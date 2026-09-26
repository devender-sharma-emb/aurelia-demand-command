"""Claude tool definitions for the agents, plus a dispatcher onto RetailWorld.

TOOLS is in the Anthropic Messages API format (name, description, input_schema).
"""
from __future__ import annotations

from . import config as C
from .world import RetailWorld

_MARKET = {"type": "string", "enum": sorted(C.MARKETS), "description": "Market code."}
_CATEGORY = {"type": "string", "enum": sorted(C.CATEGORIES), "description": "Product category."}

TOOLS: list[dict] = [
    {
        "name": "get_sales_history",
        "description": "Daily unit sales for one market and category, most recent days last.",
        "input_schema": {"type": "object", "properties": {
            "market": _MARKET, "category": _CATEGORY,
            "days": {"type": "integer", "minimum": 7, "maximum": 730, "default": 90}},
            "required": ["market", "category"]},
    },
    {
        "name": "detect_demand_spikes",
        "description": ("Find demand spikes still active on the latest data day. Leave market and category "
                        "empty to scan every market and category. Projections assume the uplift persists."),
        "input_schema": {"type": "object", "properties": {"market": _MARKET, "category": _CATEGORY}},
    },
    {
        "name": "get_inventory_position",
        "description": ("Stock for a market and category: on hand, already committed, uncommitted (free to "
                        "support a campaign), inbound units and their average arrival time in days."),
        "input_schema": {"type": "object", "properties": {"market": _MARKET, "category": _CATEGORY},
                         "required": ["market", "category"]},
    },
    {
        "name": "get_sourcing_options",
        "description": "Replenishment options (sea and air) with lead time, minimum order and estimated cost.",
        "input_schema": {"type": "object", "properties": {
            "category": _CATEGORY, "units_needed": {"type": "integer", "minimum": 1}},
            "required": ["category", "units_needed"]},
    },
    {
        "name": "get_margin",
        "description": "Average unit price, cost and margin for a market and category, weighted by recent sales.",
        "input_schema": {"type": "object", "properties": {"market": _MARKET, "category": _CATEGORY},
                         "required": ["market", "category"]},
    },
]


def dispatch(world: RetailWorld, name: str, args: dict | None = None):
    """Run a tool call. Raises ValueError with a readable message on bad input."""
    a = args or {}
    if name == "get_sales_history":
        return world.sales_history(a["market"], a["category"], a.get("days", 90))
    if name == "detect_demand_spikes":
        return world.detect_spikes(a.get("market"), a.get("category"))
    if name == "get_inventory_position":
        return world.inventory_position(a["market"], a["category"])
    if name == "get_sourcing_options":
        return world.sourcing_options(a["category"], int(a["units_needed"]))
    if name == "get_margin":
        return world.margin(a["market"], a["category"])
    raise ValueError(f"unknown tool {name!r}; valid: {[t['name'] for t in TOOLS]}")
