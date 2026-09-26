"""Deterministic campaign sizing and guardrails.

Decisions that involve money live here, in plain code, so they are reproducible and testable.
The LLM agents reason about what is happening and propose the creative shape of a campaign;
they never set spend, allocation or replenishment quantities.
"""
from __future__ import annotations

import math
from typing import Callable

from . import config as C


def plan_campaign(*, spike: dict, inventory: dict, margin: dict, other_inventory: list[dict],
                  get_sourcing: Callable[[int], list[dict]], budget: float = C.DEFAULT_BUDGET_EUR,
                  horizon_days: int = C.HORIZON_DAYS) -> dict:
    """Size a campaign to the stock that can serve it and apply the guardrails.

    spike             detect_demand_spikes result for one market and category
    inventory         get_inventory_position result for the same pair
    margin            get_margin result for the same pair
    other_inventory   get_inventory_position results for the other categories in the market
    get_sourcing      units -> get_sourcing_options result
    """
    lift = int(spike["projected_incremental_14d"])
    if lift <= 0:
        raise ValueError("projected lift must be positive to plan a campaign")

    # 1. What can be served inside the horizon
    inbound = inventory["on_order"] if inventory["on_order_eta_days"] <= horizon_days else 0
    supply = inventory["uncommitted"] + inbound
    coverage = supply / lift
    scale = min(1.0, coverage)

    # 2. Scale spend, free the rest
    spend = round(budget * scale)
    freed = round(budget - spend)

    # 3. Move part of the freed budget to the category with the most stock cover
    realloc = None
    if freed > 0:
        cands = [dict(category=o["category"], cover_days=o["uncommitted"] / max(o["avg_daily_units_28d"], 1e-9))
                 for o in other_inventory]
        if cands:
            best = max(cands, key=lambda x: x["cover_days"])
            amount = round(freed * C.REALLOC_SHARE)
            realloc = dict(category=best["category"], amount_eur=amount, cover_days=round(best["cover_days"], 1),
                           assumed_roi=C.SURPLUS_ROI)
    held = freed - (realloc["amount_eur"] if realloc else 0)

    # 4. Ask Sourcing for the shortfall, preferring an option that arrives in time
    short = max(0, math.ceil(lift - supply))
    replen = None
    if short > 0:
        opts = get_sourcing(short)
        in_time = [o for o in opts if o["lead_days"] <= horizon_days]
        pick = min(in_time, key=lambda o: o["estimated_cost_eur"]) if in_time else min(opts, key=lambda o: o["lead_days"])
        units = max(short, pick["min_order_units"])
        replen = dict(units=units, mode=pick["mode"], supplier=pick["supplier"], lead_days=pick["lead_days"],
                      estimated_cost_eur=round(pick["estimated_cost_eur"] / short * units, 2),
                      arrives_in_time=pick["lead_days"] <= horizon_days,
                      rounded_up_to_minimum=units > short)

    # 5. Guardrails
    margin_ok = margin["margin_pct"] >= C.MARGIN_FLOOR_PCT
    cap_ok = budget <= C.BUDGET_CAP_EUR
    needs_approval = freed > C.APPROVAL_LIMIT_EUR
    blocked = []
    if not margin_ok:
        blocked.append(f"margin {margin['margin_pct']}% is below the {C.MARGIN_FLOOR_PCT}% floor")
    if not cap_ok:
        blocked.append(f"budget EUR {budget:,.0f} exceeds the EUR {C.BUDGET_CAP_EUR:,.0f} cap")
    tier = "blocked" if blocked else ("needs_approval" if needs_approval else "auto_execute")

    # 6. Expected outcome (a model, not a measurement) against the same spike with no orchestrator
    mpu = margin["margin_per_unit_eur"]
    sold = min(lift, supply)
    unmet = lift - sold
    expected_margin = sold * mpu - spend + (realloc["amount_eur"] * (C.SURPLUS_ROI - 1) if realloc else 0)
    alone_margin = sold * mpu - budget
    return dict(
        market=spike["market"], category=spike["category"], horizon_days=horizon_days,
        projected_lift_units=lift, uncommitted_units=inventory["uncommitted"], inbound_in_horizon_units=inbound,
        supply_in_horizon_units=supply, coverage=round(coverage, 3), campaign_scale=round(scale, 3),
        budget_requested_eur=round(budget), spend_approved_eur=spend, freed_budget_eur=freed,
        reallocation=realloc, held_reserve_eur=held, replenishment=replen,
        allocation_units=round(lift * scale),
        guardrails=dict(
            margin_floor=dict(passed=margin_ok, margin_pct=margin["margin_pct"], floor_pct=C.MARGIN_FLOOR_PCT),
            budget_cap=dict(passed=cap_ok, budget_eur=round(budget), cap_eur=C.BUDGET_CAP_EUR),
            approval=dict(required=needs_approval, change_eur=freed, limit_eur=C.APPROVAL_LIMIT_EUR)),
        tier=tier, blocked_reasons=blocked,
        expected=dict(units_sold=round(sold), incremental_margin_eur=round(expected_margin)),
        campaign_alone=dict(units_sold=round(sold), unmet_units=round(unmet), spend_eur=round(budget),
                            wasted_spend_eur=round(budget * unmet / lift), incremental_margin_eur=round(alone_margin)),
        assumptions=[f"uplift persists for {horizon_days} days at the level of the last 3 days",
                     f"reallocated spend returns {C.SURPLUS_ROI}x (to be measured in the backtest)",
                     "inbound stock only counts if it arrives inside the horizon",
                     "replenishment ordered now is not counted as sold inside the horizon"],
    )


def max_promo_depth_pct(margin_pct: float) -> float:
    """Deepest discount that keeps the category margin at or above the floor."""
    price = 100.0
    cost = price * (1 - margin_pct / 100)
    floor_price = cost / (1 - C.MARGIN_FLOOR_PCT / 100)
    return round(max(0.0, (price - floor_price) / price * 100), 1)


def validate_campaign(proposal: dict | None, max_depth: float) -> tuple[dict, list[str]]:
    """Check an LLM campaign proposal against policy. Returns a safe proposal and a list of corrections."""
    issues: list[str] = []
    p = proposal or {}
    mix = {k: float(v) for k, v in (p.get("channel_mix") or {}).items() if k in C.CHANNELS and float(v) >= 0}
    dropped = set(p.get("channel_mix") or {}) - set(mix)
    if dropped:
        issues.append(f"removed unknown channels: {sorted(dropped)}")
    total = sum(mix.values())
    if total <= 0:
        mix, total = {k: 100.0 / len(C.CHANNELS) for k in C.CHANNELS}, 100.0
        issues.append("no valid channel mix proposed; used an even split")
    if abs(total - 100) > 0.5:
        issues.append(f"channel mix summed to {total:g}; rescaled to 100")
    mix = {k: round(v * 100 / total, 1) for k, v in mix.items()}
    offer = p.get("offer_type")
    if offer not in C.OFFER_TYPES:
        issues.append(f"offer type {offer!r} not allowed; used {C.OFFER_TYPES[0]!r}")
        offer = C.OFFER_TYPES[0]
    try:
        depth = float(p.get("promo_depth_pct", 0))
    except (TypeError, ValueError):
        depth = 0.0
    if depth > max_depth:
        issues.append(f"promo depth {depth:g}% exceeds the {max_depth:g}% allowed by the margin floor; capped")
        depth = max_depth
    return dict(channel_mix=mix, offer_type=offer, promo_depth_pct=max(0.0, depth),
                rationale=str(p.get("rationale", ""))[:500]), issues


def validate_creative(proposal: dict | None) -> tuple[dict, list[str]]:
    """Reject copy that makes claims the brand guardrails do not allow."""
    p = proposal or {}
    headline, body = str(p.get("headline", "")).strip(), str(p.get("body", "")).strip()
    issues = []
    text = f"{headline} {body}".lower()
    hits = [w for w in C.BANNED_CLAIMS if w in text]
    if hits:
        issues.append(f"banned claims: {hits}")
    if not headline or len(headline) > 90:
        issues.append("headline must be 1 to 90 characters")
    return dict(headline=headline, body=body, approved=not issues), issues
