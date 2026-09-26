"""Stand-ins for the Merchandising and Sourcing teams, implementing docs/INTERFACES.md.

Replace these with real integrations once the owning teams confirm the contracts.
"""
from __future__ import annotations

from .world import RetailWorld


class MerchandisingStub:
    def __init__(self, world: RetailWorld):
        self.world = world

    def allocate(self, req: dict) -> dict:
        free = self.world.inventory_position(req["market"], req["category"])["uncommitted"]
        granted = min(req["units_requested"], free)
        status = "accepted" if granted >= req["units_requested"] else ("partial" if granted > 0 else "rejected")
        return dict(request_id=req["request_id"], status=status, units_allocated=granted,
                    note="" if status == "accepted" else f"only {free} uncommitted units available")


class SourcingStub:
    def __init__(self, world: RetailWorld):
        self.world = world

    def replenish(self, req: dict) -> dict:
        opts = self.world.sourcing_options(req["category"], req["units_requested"])
        mode = req.get("preferred_mode", "any")
        usable = [o for o in opts if o["meets_minimum"] and (mode in ("any", o["mode"]))]
        if not usable:
            return dict(request_id=req["request_id"], status="rejected", mode=None, lead_days=None,
                        estimated_cost_eur=0.0, note="no option meets the minimum order for that mode")
        o = min(usable, key=lambda x: x["lead_days"])
        late = o["lead_days"] > req["needed_by_days"]
        return dict(request_id=req["request_id"], status="accepted", mode=o["mode"], lead_days=o["lead_days"],
                    estimated_cost_eur=o["estimated_cost_eur"],
                    note="arrives after the requested date" if late else "")
