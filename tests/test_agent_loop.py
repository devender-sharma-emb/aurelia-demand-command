import json
from types import SimpleNamespace as NS

import pytest

from aurelia.agent import AgentError, parse_json, run_agent
from aurelia.audit import AuditLog
from aurelia.llm import AnthropicClient, LLMResponse
from aurelia.tools import TOOLS


class Scripted:
    """Replays a fixed list of responses and records what it was sent."""
    def __init__(self, responses):
        self.responses, self.seen = list(responses), []

    def create(self, system, messages, tools):
        self.seen.append(json.loads(json.dumps(messages)))
        return self.responses.pop(0)


def _tool_use(name, **args):
    return LLMResponse([{"type": "tool_use", "id": "t1", "name": name, "input": args}], "tool_use")


def _text(obj):
    return LLMResponse([{"type": "text", "text": json.dumps(obj)}], "end_turn")


DEFS = [t for t in TOOLS if t["name"] == "get_margin"]


def test_loop_runs_tool_then_returns_parsed_answer():
    audit = AuditLog()
    client = Scripted([_tool_use("get_margin", market="C", category="home"), _text({"ok": True})])
    run = run_agent(client, "x", "sys", {"t": 1}, DEFS, lambda n, a: {"margin_pct": 41.3}, audit)
    assert run.output == {"ok": True}
    assert run.tool_result("get_margin") == {"margin_pct": 41.3}
    result_msg = client.seen[1][-1]["content"][0]
    assert result_msg["type"] == "tool_result" and result_msg["tool_use_id"] == "t1"
    assert [e["event"] for e in audit.entries] == ["agent_start", "tool_call", "agent_answer"]


def test_tool_outside_the_allow_list_is_refused_and_reported_to_the_model():
    audit = AuditLog()
    client = Scripted([_tool_use("get_sourcing_options", category="home", units_needed=5), _text({"done": 1})])
    run = run_agent(client, "x", "sys", {}, DEFS, lambda n, a: pytest.fail("must not dispatch"), audit)
    assert run.tool_calls[0]["is_error"] and "not available" in run.tool_calls[0]["output"]
    assert client.seen[1][-1]["content"][0]["is_error"] is True


def test_tool_errors_are_returned_not_raised():
    def boom(name, args):
        raise ValueError("unknown market 'Z'")
    client = Scripted([_tool_use("get_margin", market="Z", category="home"), _text({})])
    run = run_agent(client, "x", "sys", {}, DEFS, boom, AuditLog())
    assert run.tool_calls[0]["is_error"] and run.tool_result("get_margin") is None


def test_runaway_loop_is_stopped():
    client = Scripted([_tool_use("get_margin", market="C", category="home")] * 3)
    with pytest.raises(AgentError):
        run_agent(client, "x", "sys", {}, DEFS, lambda n, a: {}, AuditLog(), max_turns=3)


def test_parse_json_tolerates_prose_and_rejects_garbage():
    assert parse_json('Sure! {"a": 1} hope that helps') == {"a": 1}
    assert parse_json("no json here") is None and parse_json("{broken") is None


def test_anthropic_client_translates_sdk_objects():
    calls = {}

    class FakeMessages:
        def create(self, **kw):
            calls.update(kw)
            return NS(stop_reason="tool_use", content=[
                NS(type="text", text="checking"),
                NS(type="tool_use", id="tu_1", name="get_margin", input={"market": "C", "category": "home"})])

    client = AnthropicClient(model="claude-test", sdk=NS(messages=FakeMessages()))
    resp = client.create("sys", [{"role": "user", "content": "{}"}], DEFS)
    assert calls["model"] == "claude-test" and calls["tools"] == DEFS and calls["system"] == "sys"
    assert resp.stop_reason == "tool_use"
    assert resp.content[1] == {"type": "tool_use", "id": "tu_1", "name": "get_margin",
                               "input": {"market": "C", "category": "home"}}
