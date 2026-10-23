"""The only path to an LLM.

Every call is cached on disk (so reruns and repeated experiments cost nothing),
throttled per provider (to stay inside free-tier limits), retried on transient
errors, and logged with tokens, latency and cost.

Free tiers fail in bursts (rate limits, weekly caps, provider outages), so:
- rate limits back off for minutes, other transient errors for seconds;
- a provider that keeps failing is paused (cool-down) instead of failing every
  remaining question of a long run instantly;
- an alias may name a `fallback` alias serving the same model weights through another
  provider; the completion records which model string actually answered.
"""

import hashlib
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import diskcache
from pydantic import BaseModel, Field

from loupe.llm.registry import ModelRegistry, ModelSpec

MAX_ATTEMPTS = 5
REQUEST_TIMEOUT = 90  # seconds per model call
BACKOFF_SECONDS = 2.0  # connection drops and 5xx: 2, 4, 8, 16 s
RATE_LIMIT_BACKOFF = 15.0  # 429s: 15, 30, 60, 120 s
FAILS_BEFORE_COOLDOWN = 3  # consecutive failed calls (after retries) per provider
COOLDOWN_SECONDS = 300.0
# Some reasoning models put their private reasoning in the answer text. It is removed so
# answers are compared on what the model actually concludes; an unclosed block means the
# model ran out of tokens while still thinking.
THINK = re.compile(r"<think>.*?(</think>|$)", re.S)


def strip_reasoning(text: str | None) -> str | None:
    if text is None or "<think>" not in text:
        return text
    return THINK.sub("", text).strip()


class ToolCall(BaseModel):
    id: str | None = None
    name: str
    arguments: dict[str, Any]


class Completion(BaseModel):
    alias: str
    model: str
    text: str | None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    cached: bool = False


class EmptyResponseError(RuntimeError):
    """The provider answered without any completion."""


def _is_transient(exc: Exception) -> bool:
    """Worth retrying: rate limits and dropped connections. A timeout is not: a model that
    took 90 s once will likely do it again, and retrying would stall a long run."""
    import litellm

    transient = (
        litellm.RateLimitError,
        litellm.ServiceUnavailableError,
        litellm.APIConnectionError,
        litellm.InternalServerError,
    )
    return isinstance(exc, (*transient, EmptyResponseError))


class Gateway:
    def __init__(
        self,
        registry: ModelRegistry,
        cache_dir: Path,
        log_path: Path,
        completion_fn: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        patient: bool = True,
    ):
        self.registry = registry
        self.cache = diskcache.Cache(str(cache_dir / "llm"))
        self.log_path = log_path
        self._completion_fn = completion_fn
        self._sleep = sleep
        self._clock = clock
        self._last_call: dict[str, float] = {}
        self._fails: dict[str, int] = {}
        self._cool_until: dict[str, float] = {}
        # patient (experiment runs): long backoff and provider cool-downs.
        # impatient (the live Bench): 3 quick tries, then a visible error within seconds.
        self.patient = patient

    def complete(
        self,
        alias: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        use_cache: bool = True,
    ) -> Completion:
        spec = self.registry.get(alias)
        request = {
            "model": spec.model,
            "messages": messages,
            "tools": tools,
            "json_mode": json_mode,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

        if use_cache and (hit := self.cache.get(key)) is not None:
            result = Completion.model_validate(hit).model_copy(update={"cached": True})
            self._log(key, result)
            return result

        try:
            result = self._call_with_retry(spec, request)
        except Exception:
            if not spec.fallback:
                raise
            backup = self.registry.get(spec.fallback)
            result = self._call_with_retry(backup, {**request, "model": backup.model})
            result = result.model_copy(update={"alias": alias})
        self.cache.set(key, result.model_dump())
        self._log(key, result)
        return result

    def _call_with_retry(self, spec: ModelSpec, request: dict[str, Any]) -> Completion:
        import litellm

        attempts = MAX_ATTEMPTS if self.patient else 3
        for attempt in range(1, attempts + 1):
            self._throttle(spec)
            try:
                result = self._call(spec, request)
                self._fails[spec.provider] = 0
                return result
            except Exception as exc:
                self._log_error(spec, exc)
                if attempt == attempts or not _is_transient(exc):
                    self._record_failure(spec.provider)
                    raise
                limited = isinstance(exc, litellm.RateLimitError)
                base = RATE_LIMIT_BACKOFF if limited and self.patient else BACKOFF_SECONDS
                self._sleep(base * 2 ** (attempt - 1))
        raise AssertionError("unreachable")

    def _record_failure(self, provider: str) -> None:
        if not self.patient:
            return
        self._fails[provider] = self._fails.get(provider, 0) + 1
        if self._fails[provider] >= FAILS_BEFORE_COOLDOWN:
            self._cool_until[provider] = self._clock() + COOLDOWN_SECONDS
            self._fails[provider] = 0

    def _throttle(self, spec: ModelSpec) -> None:
        until = self._cool_until.pop(spec.provider, None)
        if until is not None and (wait := until - self._clock()) > 0:
            self._sleep(wait)
        if spec.rpm <= 0:
            return
        interval = 60.0 / spec.rpm
        last = self._last_call.get(spec.provider)
        if last is not None and (wait := interval - (self._clock() - last)) > 0:
            self._sleep(wait)
        self._last_call[spec.provider] = self._clock()

    def _call(self, spec: ModelSpec, request: dict[str, Any]) -> Completion:
        import litellm

        litellm.suppress_debug_info = True
        kwargs: dict[str, Any] = {
            "model": spec.model,
            "messages": request["messages"],
            "max_tokens": request["max_tokens"],
            "temperature": request["temperature"],
            "timeout": REQUEST_TIMEOUT,  # a stalled connection must not hang a long run
        }
        if request["tools"]:
            kwargs["tools"] = request["tools"]
        if request["json_mode"]:
            kwargs["response_format"] = {"type": "json_object"}
        if spec.api_base:
            kwargs["api_base"] = spec.api_base
        if spec.api_key:
            kwargs["api_key"] = spec.api_key

        fn = self._completion_fn or litellm.completion
        start = time.perf_counter()
        resp = fn(**kwargs)
        latency_ms = int((time.perf_counter() - start) * 1000)

        if not getattr(resp, "choices", None):
            # some providers (seen on OpenRouter free models) answer 200 with no choices when
            # they fail mid-request; treat it as a provider outage so it is retried
            raise EmptyResponseError(f"{spec.model} returned no choices")
        message = resp.choices[0].message
        tool_calls = [
            ToolCall(
                id=getattr(tc, "id", None),
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in (getattr(message, "tool_calls", None) or [])
        ]
        try:
            cost = float(litellm.completion_cost(completion_response=resp) or 0.0)
        except Exception:
            cost = 0.0  # free or unpriced models

        usage = getattr(resp, "usage", None)
        return Completion(
            alias=spec.alias,
            model=getattr(resp, "model", None) or spec.model,
            text=strip_reasoning(message.content),
            tool_calls=tool_calls,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

    def _log_error(self, spec: ModelSpec, exc: Exception) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(UTC).isoformat(), "alias": spec.alias, "model": spec.model,
               "error": f"{type(exc).__name__}: {str(exc)[:200]}"}  # fmt: skip
        with self.log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def _log(self, key: str, result: Completion) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(UTC).isoformat(),
            "key": key[:16],
            **result.model_dump(exclude={"text", "tool_calls"}),
        }
        with self.log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")
