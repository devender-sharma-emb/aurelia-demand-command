"""Backtest: the same demand spikes handled by "campaign alone" and by the orchestrator.

For every injected event in many seeded worlds:
  1. detect the spike from sales up to that day only (causal),
  2. draw the stock position the market would plausibly hold (same rules as the generator),
  3. size the campaign with decision.plan_campaign, the code the orchestrator uses,
  4. score both strategies against ground truth: the true extra demand over the next 14 days.

Scope: this tests the decision engine (sizing, reallocation, approval tiers). The LLM agents do not
set any of these numbers, so they are not part of the backtest.

Outcome model, stated so it can be challenged:
  * Both strategies face the same stock. Inbound stock counts only if it arrives inside the horizon.
  * Units captured are proportional to spend: sold = min(stock, true_lift * spend / full_budget).
  * Campaign alone spends the full budget. The orchestrator spends budget * min(1, stock / (projected_lift
    x sizing_factor)), so a wrong projection costs it sales. That downside is measured, not assumed away.
  * Wasted spend is the spend that chased demand the stock could not serve.
  * Freed budget moved to the surplus category returns SURPLUS_ROI (an assumption, from config).
    A conservative column shows results with that benefit removed (return of 1.0).
  * Replenishment ordered now is not counted as sold inside the horizon (no credit for it).

Calibration and evaluation use different seeds, so the sizing factor is not tuned on the data it is
judged on.

  python -m aurelia.backtest --sweep                       # calibration seeds 0-19, prints a table
  python -m aurelia.backtest --seed-start 100 --seeds 20   # held-out evaluation with the configured factor
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .decision import plan_campaign
from .detect import active_spike, find_spikes
from .generate import generate
from .world import RetailWorld

HORIZON = C.HORIZON_DAYS
FACTORS = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4]


def sample_inventory(rng: np.random.Generator, baseline_daily: float) -> dict:
    """Stock a market would hold for a category: 12 SKUs, cover and committed share drawn as in generate.py."""
    cover = rng.uniform(9, 24, C.SKUS_PER_CATEGORY)
    committed = rng.uniform(0.35, 0.60, C.SKUS_PER_CATEGORY)
    on_order = rng.uniform(0, 14, C.SKUS_PER_CATEGORY)
    return dict(uncommitted=int(round(baseline_daily * float(np.mean(cover * (1 - committed))))),
                on_order=int(round(baseline_daily * float(np.mean(on_order)))),
                on_order_eta_days=int(rng.integers(10, 36)),
                avg_daily_units_28d=float(baseline_daily))


def _detect_event(series: pd.Series, e: pd.Series):
    """First run of flagged days that overlaps the event. Returns the detection day or None."""
    start = pd.Timestamp(e["start_date"])
    end = start + pd.Timedelta(days=int(e["duration_days"]))
    for run in find_spikes(series):
        if start - pd.Timedelta(days=1) <= run["start"] <= end:
            return run["start"] + pd.Timedelta(days=2)   # known on the third flagged day
    return None


def prepare_world(seed: int) -> tuple[RetailWorld, list[dict]]:
    """Everything about each event that does not depend on the strategy being scored."""
    tables = generate(seed=seed)
    world = RetailWorld(**tables)
    rng = np.random.default_rng(10_000 + seed)
    base = {k: g.set_index(pd.to_datetime(g["date"])) for k, g in tables["baseline"].groupby(["market", "category"])}
    ctxs = []
    for _, e in tables["events"][~tables["events"]["scripted"]].iterrows():
        m, c = e["market"], e["category"]
        ctx = dict(seed=seed, event_id=e["event_id"], market=m, category=c, kind=e["kind"],
                   multiplier=e["multiplier"], duration_days=int(e["duration_days"]), detected=False)
        series = world.series(m, c)
        t = _detect_event(series, e)
        spike = active_spike(series.loc[:t]) if t is not None else None
        if spike is None or spike["projected_incremental_14d"] <= 0:
            ctxs.append(ctx)
            continue
        b = base[(m, c)]
        window = b.loc[t + pd.Timedelta(days=1): t + pd.Timedelta(days=HORIZON)]
        pre = float(b.loc[t - pd.Timedelta(days=14): t - pd.Timedelta(days=1), "baseline_units"].mean())
        others = [dict(category=oc, **sample_inventory(rng, float(base[(m, oc)].loc[t - pd.Timedelta(days=14): t, "baseline_units"].mean())))
                  for oc in C.CATEGORIES if oc != c]
        ctx.update(detected=True, detection_lag_days=int((t - pd.Timestamp(e["start_date"])).days),
                   spike=dict(market=m, category=c, projected_incremental_14d=spike["projected_incremental_14d"]),
                   true_lift=float((window["expected_units"] - window["baseline_units"]).sum()),
                   inventory=sample_inventory(rng, pre), others=others, margin=world.margin(m, c),
                   surplus_mpu={o["category"]: world.margin(m, o["category"])["margin_per_unit_eur"] for o in others})
        ctxs.append(ctx)
    return world, ctxs


def score(world: RetailWorld, ctx: dict, factor: float, budget: float) -> dict:
    row = {k: ctx[k] for k in ("seed", "event_id", "market", "category", "kind", "multiplier", "duration_days",
                               "detected")}
    row["sizing_factor"] = factor
    if not ctx["detected"]:
        return row
    c, true_lift, margin = ctx["category"], ctx["true_lift"], ctx["margin"]
    d = plan_campaign(spike=ctx["spike"], inventory=ctx["inventory"], margin=margin, other_inventory=ctx["others"],
                      get_sourcing=lambda n: world.sourcing_options(c, n), budget=budget, sizing_factor=factor)
    mpu, supply, proj = margin["margin_per_unit_eur"], d["supply_in_horizon_units"], d["projected_lift_units"]
    scale, spend = d["campaign_scale"], d["spend_approved_eur"]
    a_sold, o_sold = min(supply, true_lift), min(supply, true_lift * scale)
    a_waste = budget * max(0.0, 1 - supply / true_lift)
    o_waste = spend * max(0.0, 1 - supply / (true_lift * scale)) if true_lift * scale > 0 else spend
    realloc = d["reallocation"]
    r_amt = realloc["amount_eur"] if realloc else 0
    r_units = r_amt * C.SURPLUS_ROI / ctx["surplus_mpu"][realloc["category"]] if realloc else 0.0
    r_gain = r_amt * (C.SURPLUS_ROI - 1)
    a_margin, o_cons = a_sold * mpu - budget, o_sold * mpu - spend
    row.update(
        detection_lag_days=ctx["detection_lag_days"], projected_lift=proj, true_lift=round(true_lift, 1),
        projection_error_pct=round(100 * (proj - true_lift) / true_lift, 1),
        uncommitted=ctx["inventory"]["uncommitted"], supply=supply, coverage_true=round(supply / true_lift, 3),
        coverage_est=d["coverage"], scale=scale, tier=d["tier"],
        alone_spend=round(budget), alone_sold=round(a_sold, 1), alone_unmet=round(true_lift - a_sold, 1),
        alone_wasted=round(a_waste), alone_margin=round(a_margin),
        orch_spend=spend, orch_sold=round(o_sold, 1), orch_unmet=round(true_lift - o_sold, 1),
        orch_wasted=round(o_waste), orch_margin=round(o_cons + r_gain), orch_margin_conservative=round(o_cons),
        realloc_eur=r_amt, markdown_units_avoided=round(r_units, 1),
        uplift=round(o_cons + r_gain - a_margin), uplift_conservative=round(o_cons - a_margin))
    return row


def _ci(x: np.ndarray, rng: np.random.Generator, n: int = 4000) -> list[float]:
    means = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return [round(float(np.percentile(means, 2.5))), round(float(np.percentile(means, 97.5)))]


def _block(df: pd.DataFrame, rng: np.random.Generator) -> dict:
    if df.empty:
        return dict(n=0)
    return dict(
        n=int(len(df)),
        alone=dict(margin_per_spike_eur=round(df["alone_margin"].mean()), lost_units_per_spike=round(df["alone_unmet"].mean()),
                   wasted_spend_per_spike_eur=round(df["alone_wasted"].mean()), markdown_units_avoided_per_spike=0),
        orchestrated=dict(margin_per_spike_eur=round(df["orch_margin"].mean()), lost_units_per_spike=round(df["orch_unmet"].mean()),
                          wasted_spend_per_spike_eur=round(df["orch_wasted"].mean()),
                          markdown_units_avoided_per_spike=round(df["markdown_units_avoided"].mean())),
        margin_uplift_per_spike_eur=round(df["uplift"].mean()), margin_uplift_ci95=_ci(df["uplift"].to_numpy(float), rng),
        conservative_uplift_per_spike_eur=round(df["uplift_conservative"].mean()),
        conservative_uplift_ci95=_ci(df["uplift_conservative"].to_numpy(float), rng),
        share_of_spikes_orchestrator_better=round(float((df["uplift"] > 0).mean()), 3),
        share_of_spikes_orchestrator_better_conservative=round(float((df["uplift_conservative"] > 0).mean()), 3),
    )


def summarize(df: pd.DataFrame, seeds: list[int], budget: float, factor: float) -> dict:
    rng = np.random.default_rng(0)
    det = df[df["detected"]]
    return dict(
        setup=dict(seeds=f"{seeds[0]}..{seeds[-1]}", n_seeds=len(seeds), events=int(len(df)), budget_eur=budget,
                   horizon_days=HORIZON, sizing_factor=factor, surplus_roi_assumed=C.SURPLUS_ROI,
                   approval_limit_eur=C.APPROVAL_LIMIT_EUR),
        detection=dict(detected=int(df["detected"].sum()), of=int(len(df)), rate=round(float(df["detected"].mean()), 3),
                       median_lag_days=float(det["detection_lag_days"].median())),
        projection=dict(median_abs_error_pct=round(float(det["projection_error_pct"].abs().median()), 1),
                        mean_signed_error_pct=round(float(det["projection_error_pct"].mean()), 1),
                        share_overestimated=round(float((det["projection_error_pct"] > 0).mean()), 3)),
        approvals=dict(share_needing_human_approval=round(float((det["tier"] == "needs_approval").mean()), 3)),
        all_detected=_block(det, rng),
        stock_short=_block(det[det["coverage_true"] < 1], rng),
        stock_sufficient=_block(det[det["coverage_true"] >= 1], rng),
    )


def evaluate(seeds: list[int], factors: list[float], budget: float) -> pd.DataFrame:
    rows = []
    for s in seeds:
        world, ctxs = prepare_world(s)
        rows += [score(world, ctx, f, budget) for ctx in ctxs for f in factors]
    return pd.DataFrame(rows)


def sweep(seeds: list[int], budget: float) -> pd.DataFrame:
    df = evaluate(seeds, FACTORS, budget)
    det = df[df["detected"]]
    g = det.groupby("sizing_factor")
    return pd.DataFrame(dict(
        n=g.size(), uplift_conservative=g["uplift_conservative"].mean().round(),
        uplift_with_realloc=g["uplift"].mean().round(), wasted_alone=g["alone_wasted"].mean().round(),
        wasted_orch=g["orch_wasted"].mean().round(), lost_alone=g["alone_unmet"].mean().round(),
        lost_orch=g["orch_unmet"].mean().round(), spend_orch=g["orch_spend"].mean().round())).reset_index()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--seed-start", type=int, default=100, help="held-out evaluation seeds start here")
    p.add_argument("--budget", type=float, default=C.DEFAULT_BUDGET_EUR)
    p.add_argument("--factor", type=float, default=C.LIFT_SIZING_FACTOR)
    p.add_argument("--sweep", action="store_true", help="calibrate the sizing factor on seeds 0-19")
    p.add_argument("--out", default="data/backtest")
    a = p.parse_args()
    if a.sweep:
        print(sweep(list(range(20)), a.budget).to_string(index=False))
        return
    seeds = list(range(a.seed_start, a.seed_start + a.seeds))
    df = evaluate(seeds, [a.factor], a.budget)
    summary = summarize(df, seeds, a.budget, a.factor)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "backtest_events.csv", index=False)
    (out / "backtest_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
