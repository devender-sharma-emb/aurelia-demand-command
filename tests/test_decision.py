import pytest

from aurelia import config as C
from aurelia.decision import max_promo_depth_pct, plan_campaign, validate_campaign, validate_creative


def _inputs(uncommitted=3000, lift=5000, on_order=0, eta=24, margin_pct=40.0, mpu=30.0):
    spike = dict(market="C", category="home", projected_incremental_14d=lift)
    inv = dict(uncommitted=uncommitted, on_order=on_order, on_order_eta_days=eta)
    margin = dict(margin_pct=margin_pct, margin_per_unit_eur=mpu)
    others = [dict(category="beauty", uncommitted=9000, avg_daily_units_28d=300),
              dict(category="clothing", uncommitted=2000, avg_daily_units_28d=300)]
    opts = lambda n: [dict(mode="air", supplier="S", lead_days=7, min_order_units=200, estimated_cost_eur=n * 50.0),
                      dict(mode="sea", supplier="S", lead_days=40, min_order_units=2000, estimated_cost_eur=n * 42.0)]
    return dict(spike=spike, inventory=inv, margin=margin, other_inventory=others, get_sourcing=opts)


def test_scales_spend_to_stock_and_frees_the_rest():
    d = plan_campaign(**_inputs(uncommitted=3000, lift=5000), budget=40_000)
    assert d["coverage"] == 0.6 and d["campaign_scale"] == 0.6
    assert d["spend_approved_eur"] == 24_000 and d["freed_budget_eur"] == 16_000
    assert d["allocation_units"] == 3000
    assert d["reallocation"]["category"] == "beauty"          # highest days of cover
    assert d["reallocation"]["amount_eur"] == 9_600           # 60% of freed budget
    assert d["held_reserve_eur"] == 6_400
    assert d["reallocation"]["amount_eur"] + d["held_reserve_eur"] == d["freed_budget_eur"]


def test_approval_gate_at_the_limit():
    over = plan_campaign(**_inputs(uncommitted=3000), budget=40_000)      # freed 16,000
    assert over["tier"] == "needs_approval"
    at = plan_campaign(**_inputs(uncommitted=3125), budget=40_000)        # freed exactly 15,000
    assert at["freed_budget_eur"] == C.APPROVAL_LIMIT_EUR and at["tier"] == "auto_execute"


def test_full_coverage_needs_no_reallocation_or_replenishment():
    d = plan_campaign(**_inputs(uncommitted=6000, lift=5000))
    assert d["campaign_scale"] == 1.0 and d["freed_budget_eur"] == 0
    assert d["reallocation"] is None and d["replenishment"] is None and d["tier"] == "auto_execute"


def test_replenishment_prefers_option_that_arrives_in_time():
    d = plan_campaign(**_inputs(uncommitted=3000, lift=5000))
    r = d["replenishment"]
    assert (r["mode"], r["units"], r["arrives_in_time"]) == ("air", 2000, True)


def test_replenishment_rounds_up_to_minimum_order():
    d = plan_campaign(**_inputs(uncommitted=4950, lift=5000))
    r = d["replenishment"]
    assert r["units"] == 200 and r["rounded_up_to_minimum"]
    assert r["estimated_cost_eur"] == pytest.approx(200 * 50.0)


def test_inbound_stock_counts_only_if_it_arrives_in_time():
    late = plan_campaign(**_inputs(uncommitted=3000, on_order=2000, eta=24))
    early = plan_campaign(**_inputs(uncommitted=3000, on_order=2000, eta=10))
    assert late["supply_in_horizon_units"] == 3000 and early["supply_in_horizon_units"] == 5000


def test_guardrails_block_low_margin_and_oversized_budget():
    low = plan_campaign(**_inputs(margin_pct=10.0))
    assert low["tier"] == "blocked" and "margin" in low["blocked_reasons"][0]
    big = plan_campaign(**_inputs(), budget=C.BUDGET_CAP_EUR + 1)
    assert big["tier"] == "blocked" and "cap" in big["blocked_reasons"][0]


def test_orchestrated_outcome_beats_campaign_alone_when_stock_is_short():
    d = plan_campaign(**_inputs(uncommitted=3000, lift=5000), budget=40_000)
    assert d["campaign_alone"]["unmet_units"] == 2000
    assert d["campaign_alone"]["wasted_spend_eur"] == 16_000
    assert d["expected"]["incremental_margin_eur"] > d["campaign_alone"]["incremental_margin_eur"]


def test_no_positive_lift_is_an_error():
    with pytest.raises(ValueError):
        plan_campaign(**_inputs(lift=0))


def test_max_promo_depth_keeps_margin_at_the_floor():
    depth = max_promo_depth_pct(40.0)
    price = 100 * (1 - depth / 100)
    cost = 60.0
    assert (price - cost) / price * 100 == pytest.approx(C.MARGIN_FLOOR_PCT, abs=0.2)
    assert max_promo_depth_pct(10.0) == 0.0


def test_validate_campaign_corrects_unsafe_proposals():
    bad = dict(channel_mix=dict(paid_search=70, tiktok=30, email=30), offer_type="mystery", promo_depth_pct=35)
    clean, issues = validate_campaign(bad, max_depth=20.0)
    assert set(clean["channel_mix"]) == {"paid_search", "email"}
    assert sum(clean["channel_mix"].values()) == pytest.approx(100, abs=0.2)
    assert clean["offer_type"] in C.OFFER_TYPES and clean["promo_depth_pct"] == 20.0
    assert len(issues) == 3   # unknown channel, unknown offer, promo depth cap
    _, none = validate_campaign(dict(channel_mix=dict(email=100), offer_type="bundle", promo_depth_pct=5), 20.0)
    assert none == []


def test_validate_creative_rejects_banned_claims():
    ok, issues = validate_creative(dict(headline="Refresh your home for less", body="While stock lasts."))
    assert ok["approved"] and not issues
    bad, issues = validate_creative(dict(headline="The cheapest home deals, guaranteed", body="x"))
    assert not bad["approved"] and "banned claims" in issues[0]
