"""A small tool-use loop with least-privilege tools and a full audit trail."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .audit import AuditLog
from .llm import LLMClient


class AgentError(RuntimeError):
    pass


@dataclass
class AgentRun:
    agent: str
    final_text: str
    output: dict | None            # parsed JSON answer, None if the agent did not return valid JSON
    tool_calls: list[dict] = field(default_factory=list)

    def tool_result(self, name: str):
        """Latest successful result of a tool, taken from the tool call itself and not from the model's text."""
        for c in reversed(self.tool_calls):
            if c["name"] == name and not c["is_error"]:
                return c["output"]
        return None


def parse_json(text: str) -> dict | None:
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        obj = json.loads(text[i:j + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def run_agent(client: LLMClient, agent: str, system: str, task: dict, tool_defs: list[dict],
              dispatch: Callable[[str, dict], object], audit: AuditLog, max_turns: int = 6) -> AgentRun:
    allowed = {t["name"] for t in tool_defs}
    messages = [{"role": "user", "content": json.dumps(task)}]
    calls: list[dict] = []
    audit.log(agent, "agent_start", {"task": task, "tools": sorted(allowed)})
    for _ in range(max_turns):
        resp = client.create(system=system, messages=messages, tools=tool_defs)
        messages.append({"role": "assistant", "content": resp.content})
        uses = [b for b in resp.content if b["type"] == "tool_use"]
        if not uses:
            text = "".join(b["text"] for b in resp.content if b["type"] == "text")
            run = AgentRun(agent, text, parse_json(text), calls)
            audit.log(agent, "agent_answer", {"output": run.output, "valid_json": run.output is not None})
            return run
        results = []
        for u in uses:
            try:
                if u["name"] not in allowed:
                    raise PermissionError(f"tool {u['name']!r} is not available to the {agent} agent")
                out, err = dispatch(u["name"], u["input"]), False
                content = json.dumps(out)
            except Exception as exc:  # returned to the model so it can correct itself
                out, err = f"{type(exc).__name__}: {exc}", True
                content = out
            calls.append(dict(name=u["name"], input=u["input"], output=out, is_error=err))
            audit.log(agent, "tool_call", dict(name=u["name"], input=u["input"], is_error=err))
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": content, "is_error": err})
        messages.append({"role": "user", "content": results})
    raise AgentError(f"{agent} agent did not finish within {max_turns} turns")
