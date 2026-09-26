import pytest

from aurelia import config as C
from aurelia.backtest import prepare_world, score, summarize
import pandas as pd


@pytest.fixture(scope="module")
def prepared():
    return prepare_world(0)


def test_most_events_are_detected_before_scoring(prepared):
    _, ctxs = prepared
    assert sum(c["detected"] for c in ctxs) >= 22 and len(ctxs) == 24


def test_scoring_invariants(prepared):
    world, ctxs = prepared
    for ctx in [c for c in ctxs if c["detected"]]:
        r = score(world, ctx, 0.8, C.DEFAULT_BUDGET_EUR)
        assert r["orch_spend"] <= r["alone_spend"] == C.DEFAULT_BUDGET_EUR
        assert r["alone_sold"] <= r["supply"] + 1e-6 and r["orch_sold"] <= r["supply"] + 1e-6
        assert r["orch_wasted"] >= 0 and r["alone_wasted"] >= 0 and r["true_lift"] > 0
        # Same stock, same demand: with full coverage the orchestrator changes nothing except the cost of caution.
        if r["scale"] >= 0.999:
            assert r["orch_spend"] == pytest.approx(r["alone_spend"], rel=2e-3)


def test_scoring_is_deterministic(prepared):
    world, ctxs = prepared
    ctx = next(c for c in ctxs if c["detected"])
    assert score(world, ctx, 0.8, 40_000) == score(world, ctx, 0.8, 40_000)


def test_summary_has_the_reported_blocks(prepared):
    world, ctxs = prepared
    df = pd.DataFrame([score(world, c, 0.8, 40_000) for c in ctxs])
    s = summarize(df, [0], 40_000, 0.8)
    assert set(s) >= {"setup", "detection", "projection", "approvals", "all_detected", "stock_short", "stock_sufficient"}
    lo, hi = s["all_detected"]["margin_uplift_ci95"]
    assert lo <= s["all_detected"]["margin_uplift_per_spike_eur"] <= hi
