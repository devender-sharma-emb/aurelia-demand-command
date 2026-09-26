"""LLM client interface.

Messages and content blocks use the Anthropic Messages API shape, so AnthropicClient is a thin
pass-through. OfflineClient is a deterministic stand-in that follows the same protocol. It is NOT a
language model: it exists so the whole pipeline can run and be tested without an API key.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol

from . import config as C

DEFAULT_MODEL = "claude-sonnet-5"


@dataclass
class LLMResponse:
    content: list[dict]      # {"type": "text", "text": ...} or {"type": "tool_use", "id", "name", "input"}
    stop_reason: str         # "tool_use" or "end_turn"


class LLMClient(Protocol):
    def create(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse: ...


class AnthropicClient:
    """Calls the Anthropic Messages API. Pass `sdk` to inject a client (used in tests)."""

    def __init__(self, model: str | None = None, max_tokens: int = 1024, sdk=None):
        self.model = model or os.environ.get("AURELIA_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        if sdk is None:
            import anthropic  # imported lazily so offline use needs no SDK
            sdk = anthropic.Anthropic()
        self.sdk = sdk

    def create(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        kwargs = dict(model=self.model, max_tokens=self.max_tokens, system=system, messages=messages)
        if tools:
            kwargs["tools"] = tools
        resp = self.sdk.messages.create(**kwargs)
        blocks = []
        for b in resp.content:
            if b.type == "text":
                blocks.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input)})
        return LLMResponse(blocks, resp.stop_reason)


class OfflineClient:
    """Deterministic stand-in for the four LLM agents. Picks tool calls and writes structured
    answers from the tool results, with no model involved."""

    def __init__(self):
        self._n = 0

    def create(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        agent = re.search(r"\[agent:(\w+)\]", system).group(1)
        task = json.loads(messages[0]["content"])
        blocks = [b for m in messages[1:] if m["role"] == "user" for b in m["content"]
                  if b.get("type") == "tool_result"]
        results = [json.loads(b["content"]) for b in blocks if not b.get("is_error")]
        if blocks and not results and agent in ("sensing", "segmentation"):
            return LLMResponse([{"type": "text", "text": json.dumps(dict(
                spike_confirmed=False, summary=f"Tool call failed: {blocks[-1]['content']}", confidence="low",
                likely_driver="unknown", value_seeking_share=None, recommended_offer_style="loyalty_points"))}],
                "end_turn")

        def tool(name, **args):
            self._n += 1
            return LLMResponse([{"type": "tool_use", "id": f"toolu_offline_{self._n}", "name": name, "input": args}],
                               "tool_use")

        def say(obj):
            return LLMResponse([{"type": "text", "text": json.dumps(obj)}], "end_turn")

        m, c = task.get("market"), task.get("category")
        if agent == "sensing":
            if not results:
                return tool("detect_demand_spikes", market=m, category=c)
            sp = results[0][0] if results[0] else None
            if not sp:
                return say(dict(spike_confirmed=False, summary="No active spike.", likely_driver="none",
                                confidence="high"))
            return say(dict(spike_confirmed=True, likely_driver="unknown from sales data alone",
                            confidence="high" if sp["peak_z"] > 5 else "medium",
                            summary=(f"{c} demand in market {m} is running {sp['uplift_ratio']}x baseline for "
                                     f"{sp['days_active']} days. Projected +{sp['projected_incremental_14d']} units "
                                     f"over 14 days if it persists.")))
        if agent == "segmentation":
            if not results:
                return tool("get_segment_mix", market=m, category=c)
            mix = results[0]
            vs = mix.get("value_seeking_share_of_uplift")
            style = "bundle" if vs and vs >= 0.5 else "loyalty_points"
            return say(dict(summary=("Uplift is led by value-seeking shoppers." if style == "bundle"
                                     else "Uplift is not mainly value-seeking; avoid deep discounts."),
                            value_seeking_share=vs, recommended_offer_style=style))
        if agent == "campaign":
            lim = task["limits"]
            style = task["segment_hint"] if task["segment_hint"] in lim["offer_types"] else lim["offer_types"][0]
            depth = min(10.0, lim["max_promo_depth_pct"])
            return say(dict(channel_mix=dict(paid_search=30, paid_social=25, email=25, app_push=10, onsite=10),
                            offer_type=style, promo_depth_pct=depth,
                            rationale=f"{style} keeps margin above the floor while answering value-seeking demand."))
        if agent == "creative":
            return say(dict(headline=f"Refresh your {c} for less", language_note="market-specific translation needed",
                            body=f"Bundle offers on {c} essentials, available while stock lasts."))
        raise ValueError(f"unknown agent {agent!r}")
