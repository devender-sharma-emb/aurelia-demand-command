"""The four LLM agents. Each has a narrow job, a short list of tools and a required JSON answer.

Numbers in the answers are never trusted directly. The orchestrator takes figures from the tool
results and uses the agent text for reasoning and for the creative shape of the campaign.
"""
from __future__ import annotations

from . import config as C
from .tools import TOOLS

_COMMON = ("Use only numbers that appear in tool results or in the task. Never invent figures. "
           "Reply with one JSON object and nothing else.")

AGENTS: dict[str, dict] = {
    "sensing": dict(
        tools=["detect_demand_spikes", "get_sales_history"],
        system=("[agent:sensing] You are the Demand Sensing Agent for a multi-market retailer. Confirm whether "
                "the market and category in the task have an active demand spike and describe it. " + _COMMON +
                ' Schema: {"spike_confirmed": bool, "summary": str, "likely_driver": str, '
                '"confidence": "low|medium|high"}. Say the driver is unknown if the data does not show it.')),
    "segmentation": dict(
        tools=["get_segment_mix"],
        system=("[agent:segmentation] You are the Value-Seeker Segmentation Agent. Explain which customer "
                "segments drive the uplift and recommend an offer style from: " + ", ".join(C.OFFER_TYPES) + ". " +
                _COMMON + ' Schema: {"summary": str, "value_seeking_share": number|null, '
                '"recommended_offer_style": str}.')),
    "campaign": dict(
        tools=[],
        system=("[agent:campaign] You are the Campaign and Promo Agent. Propose a channel mix, an offer type and "
                "a promo depth for the campaign described in the task. Respect task.limits: channels must come "
                "from limits.channels and sum to 100, offer_type from limits.offer_types, and promo_depth_pct "
                "must not exceed limits.max_promo_depth_pct. " + _COMMON +
                ' Schema: {"channel_mix": {channel: percent}, "offer_type": str, "promo_depth_pct": number, '
                '"rationale": str}.')),
    "creative": dict(
        tools=[],
        system=("[agent:creative] You are the Creative and Localization Agent. Write one on-brand headline "
                "(90 characters or fewer) and a short body for the campaign in the task. Do not use absolute "
                "claims such as " + ", ".join(repr(w) for w in C.BANNED_CLAIMS) + ". " + _COMMON +
                ' Schema: {"headline": str, "body": str, "language_note": str}.')),
}


def tool_defs(agent: str) -> list[dict]:
    names = set(AGENTS[agent]["tools"])
    return [t for t in TOOLS if t["name"] in names]
