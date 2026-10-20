"""The only path to an LLM.

Every call is cached on disk (so reruns and repeated experiments cost nothing),
throttled per provider (to stay inside free-tier limits), retried on transient
errors, and logged with tokens, latency and cost.
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
BACKOFF_SECONDS = 2.0
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
    return isinstance(exc, transient)


class Gateway:
    def __init__(
        self,
        registry: ModelRegistry,
        cache_dir: Path,
        log_path: Path,
        completion_fn: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.registry = registry
        self.cache = diskcache.Cache(str(cache_dir / "llm"))
        self.log_path = log_path
        self._completion_fn = completion_fn
        self._sleep = sleep
        self._clock = clock
        self._last_call: dict[str, float] = {}

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

        result = self._call_with_retry(spec, request)
        self.cache.set(key, result.model_dump())
        self._log(key, result)
        return result

    def _call_with_retry(self, spec: ModelSpec, request: dict[str, Any]) -> Completion:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._throttle(spec)
            try:
                return self._call(spec, request)
            except Exception as exc:
                if attempt == MAX_ATTEMPTS or not _is_transient(exc):
                    raise
                self._sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
        raise AssertionError("unreachable")

    def _throttle(self, spec: ModelSpec) -> None:
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

    def _log(self, key: str, result: Completion) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(UTC).isoformat(),
            "key": key[:16],
            **result.model_dump(exclude={"text", "tool_calls"}),
        }
        with self.log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")
