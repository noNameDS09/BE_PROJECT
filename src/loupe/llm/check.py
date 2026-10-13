"""Capability probe for each registered model: reachable, tool calling, JSON mode."""

import json
from typing import Literal

from pydantic import BaseModel

from loupe.llm.gateway import Gateway
from loupe.llm.registry import ModelSpec

Status = Literal["ok", "fail", "skip"]

ADD_TOOL = {
    "type": "function",
    "function": {
        "name": "add",
        "description": "Add two numbers.",
        "parameters": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
}


class ModelReport(BaseModel):
    alias: str
    model: str
    reachable: Status = "skip"
    tools: Status = "skip"
    json_mode: Status = "skip"
    latency_ms: int | None = None
    note: str = ""


def probe(gateway: Gateway, spec: ModelSpec) -> ModelReport:
    report = ModelReport(alias=spec.alias, model=spec.model)
    if key := spec.missing_key():
        report.note = f"{key} not set"
        return report

    try:
        reply = gateway.complete(
            spec.alias,
            [{"role": "user", "content": "Reply with exactly the word OK."}],
            max_tokens=10,
            use_cache=False,
        )
    except Exception as exc:
        report.reachable = "fail"
        report.note = f"{type(exc).__name__}: {str(exc)[:120]}"
        return report
    report.reachable = "ok" if reply.text and "OK" in reply.text.upper() else "fail"
    report.latency_ms = reply.latency_ms

    try:
        reply = gateway.complete(
            spec.alias,
            [{"role": "user", "content": "Use the add tool to add 2 and 3."}],
            tools=[ADD_TOOL],
            max_tokens=100,
            use_cache=False,
        )
        report.tools = "ok" if any(tc.name == "add" for tc in reply.tool_calls) else "fail"
    except Exception as exc:
        report.tools = "fail"
        report.note = f"tools: {type(exc).__name__}"

    try:
        reply = gateway.complete(
            spec.alias,
            [{"role": "user", "content": 'Return a JSON object {"answer": 5} and nothing else.'}],
            json_mode=True,
            max_tokens=50,
            use_cache=False,
        )
        report.json_mode = "ok" if json.loads(reply.text or "").get("answer") == 5 else "fail"
    except Exception as exc:
        report.json_mode = "fail"
        report.note = report.note or f"json: {type(exc).__name__}"

    return report
