import json
from types import SimpleNamespace

import pytest

from loupe.llm import Gateway, ModelRegistry, ModelSpec


def fake_response(content="OK", tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    usage = SimpleNamespace(prompt_tokens=7, completion_tokens=2)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage, model="m")


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def registry():
    return ModelRegistry(
        {
            "fast": ModelSpec(alias="fast", model="groq/x", provider="groq", rpm=0),
            "slow": ModelSpec(alias="slow", model="gemini/y", provider="gemini", rpm=6),
        }
    )


def make_gateway(tmp_path, registry, llm, sleeps=None, clock=lambda: 0.0):
    return Gateway(
        registry,
        cache_dir=tmp_path / "cache",
        log_path=tmp_path / "logs" / "calls.jsonl",
        completion_fn=llm,
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
        clock=clock,
    )


def test_second_identical_call_is_served_from_cache(tmp_path, registry):
    llm = FakeLLM([fake_response("OK")])
    gw = make_gateway(tmp_path, registry, llm)
    msgs = [{"role": "user", "content": "hi"}]

    first = gw.complete("fast", msgs)
    second = gw.complete("fast", msgs)

    assert len(llm.calls) == 1
    assert (first.cached, second.cached) == (False, True)
    assert second.text == "OK" and second.tokens_in == 7
    log = (tmp_path / "logs" / "calls.jsonl").read_text()
    rows = [json.loads(line) for line in log.splitlines()]
    assert [r["cached"] for r in rows] == [False, True]


def test_different_parameters_are_not_shared_in_cache(tmp_path, registry):
    llm = FakeLLM([fake_response("a"), fake_response("b")])
    gw = make_gateway(tmp_path, registry, llm)
    msgs = [{"role": "user", "content": "hi"}]

    assert gw.complete("fast", msgs, max_tokens=10).text == "a"
    assert gw.complete("fast", msgs, max_tokens=20).text == "b"


def test_tool_calls_are_parsed(tmp_path, registry):
    tc = SimpleNamespace(id="1", function=SimpleNamespace(name="add", arguments='{"a": 2, "b": 3}'))
    gw = make_gateway(tmp_path, registry, FakeLLM([fake_response(None, [tc])]))

    result = gw.complete("fast", [{"role": "user", "content": "add"}], tools=[{"type": "function"}])

    assert result.tool_calls[0].name == "add"
    assert result.tool_calls[0].arguments == {"a": 2, "b": 3}


def test_transient_errors_are_retried_with_backoff(tmp_path, registry):
    import litellm

    err = litellm.RateLimitError(message="429", llm_provider="groq", model="x")
    llm = FakeLLM([err, err, fake_response("OK")])
    sleeps = []
    gw = make_gateway(tmp_path, registry, llm, sleeps=sleeps)

    assert gw.complete("fast", [{"role": "user", "content": "hi"}]).text == "OK"
    assert sleeps == [15.0, 30.0]  # rate limits back off for longer than dropped connections


def test_connection_errors_back_off_briefly(tmp_path, registry):
    import litellm

    err = litellm.APIConnectionError(message="reset", llm_provider="groq", model="x")
    sleeps = []
    gw = make_gateway(tmp_path, registry, FakeLLM([err, fake_response("OK")]), sleeps=sleeps)
    assert gw.complete("fast", [{"role": "user", "content": "hi"}]).text == "OK"
    assert sleeps == [2.0]


def test_non_transient_errors_are_raised_immediately(tmp_path, registry):
    llm = FakeLLM([ValueError("bad request")])
    gw = make_gateway(tmp_path, registry, llm)

    with pytest.raises(ValueError):
        gw.complete("fast", [{"role": "user", "content": "hi"}])
    assert len(llm.calls) == 1


def test_calls_are_throttled_to_the_provider_rpm(tmp_path, registry):
    llm = FakeLLM([fake_response("a"), fake_response("b")])
    sleeps = []
    gw = make_gateway(tmp_path, registry, llm, sleeps=sleeps, clock=lambda: 100.0)

    gw.complete("slow", [{"role": "user", "content": "1"}])
    gw.complete("slow", [{"role": "user", "content": "2"}])

    assert sleeps == [10.0]  # rpm 6 -> one call per 10 s


def test_reasoning_blocks_are_stripped_from_answers():
    from loupe.llm.gateway import strip_reasoning

    assert strip_reasoning("<think>hmm, 2+2</think>\nThe answer is 4.") == "The answer is 4."
    assert strip_reasoning("<think>still thinking when tokens ran out") == ""
    assert strip_reasoning("No reasoning here.") == "No reasoning here."


def test_failing_provider_falls_back_to_the_same_model_elsewhere(tmp_path):
    import litellm

    reg = ModelRegistry({
        "nim-x": ModelSpec(alias="nim-x", model="nvidia_nim/x", provider="nvidia_nim",
                           fallback="or-x"),
        "or-x": ModelSpec(alias="or-x", model="openrouter/x:free", provider="openrouter"),
    })  # fmt: skip
    down = litellm.InternalServerError(message="500", llm_provider="nvidia_nim", model="x")
    llm = FakeLLM([down] * 5 + [fake_response("OK")])
    gw = make_gateway(tmp_path, reg, llm)
    result = gw.complete("nim-x", [{"role": "user", "content": "hi"}])
    assert result.text == "OK" and result.alias == "nim-x"
    assert [c["model"] for c in llm.calls] == ["nvidia_nim/x"] * 5 + ["openrouter/x:free"]


def test_a_provider_that_keeps_failing_is_paused(tmp_path):
    reg = ModelRegistry({"a": ModelSpec(alias="a", model="p/a", provider="p")})
    t = [0.0]
    sleeps = []
    gw = Gateway(reg, cache_dir=tmp_path / "c", log_path=tmp_path / "l.jsonl",
                 completion_fn=FakeLLM([ValueError("x")] * 3 + [fake_response("OK")]),
                 sleep=sleeps.append, clock=lambda: t[0])  # fmt: skip
    for i in range(3):
        with pytest.raises(ValueError):
            gw.complete("a", [{"role": "user", "content": str(i)}])
    assert gw.complete("a", [{"role": "user", "content": "next"}]).text == "OK"
    assert sleeps == [300.0]  # cool-down before the next call to that provider


def test_any_openrouter_model_id_resolves_without_config():
    reg = ModelRegistry({})
    alias = "openrouter/google/gemma-4-26b-a4b-it:free"
    spec = reg.get(alias)
    assert (spec.provider, spec.model) == ("openrouter", alias)
    with pytest.raises(KeyError):
        reg.get("openrouter/")
    with pytest.raises(KeyError):
        reg.get("not-a-model")


def test_live_mode_fails_fast_without_long_waits_or_cooldown(tmp_path, registry):
    import litellm

    err = litellm.RateLimitError(message="429", llm_provider="groq", model="x")
    sleeps = []
    gw = Gateway(registry, cache_dir=tmp_path / "c", log_path=tmp_path / "l.jsonl",
                 completion_fn=FakeLLM([err] * 3 + [err] * 3), sleep=sleeps.append,
                 clock=lambda: 0.0, patient=False)  # fmt: skip
    for q in ("a", "b"):
        with pytest.raises(litellm.RateLimitError):
            gw.complete("fast", [{"role": "user", "content": q}])
    assert sleeps == [2.0, 4.0, 2.0, 4.0]  # no 15-120 s backoff, no 5-minute cool-down
    errors = [json.loads(x) for x in (tmp_path / "l.jsonl").read_text().splitlines()]
    assert len(errors) == 6 and errors[0]["error"].startswith("RateLimitError")
