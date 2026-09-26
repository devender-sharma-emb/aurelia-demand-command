"""Seeded generator for the synthetic Aurelia dataset.

Produces five tables:
  sales      daily units per market and SKU, with injected demand events
  skus       price and unit cost per SKU
  inventory  stock position per market and SKU on the last data day
  sourcing   replenishment options per category
  events     ground truth for every injected demand event (used to test detection)

Run:  python -m aurelia.generate --out data/synthetic
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C


def _annual(doy: np.ndarray, amp: float, peak_day: int) -> np.ndarray:
    return 1.0 + amp * np.cos(2 * np.pi * (doy - peak_day) / 365.25)


def _pick_events(rng: np.random.Generator, n_days: int, n_random: int) -> list[dict]:
    """Scripted demo event first, then random events that never overlap it or each other."""
    demo_start = n_days - C.DEMO_DAYS_AGO
    events = [dict(market=C.DEMO_MARKET, category=C.DEMO_CATEGORY, kind="competitor_price_cut",
                   start=demo_start, duration=60, multiplier=C.DEMO_MULTIPLIER,
                   ramp=C.DEMO_RAMP_DAYS, scripted=True)]
    markets, cats = list(C.MARKETS), list(C.CATEGORIES)
    tries = 0
    while len(events) < n_random + 1 and tries < 5000:
        tries += 1
        ev = dict(market=str(rng.choice(markets)), category=str(rng.choice(cats)),
                  kind=str(rng.choice(C.EVENT_KINDS)),
                  start=int(rng.integers(70, n_days - 45)), duration=int(rng.integers(10, 22)),
                  multiplier=round(float(rng.uniform(1.5, 2.5)), 2), ramp=3, scripted=False)
        clash = any(e["market"] == ev["market"] and e["category"] == ev["category"]
                    and abs(e["start"] - ev["start"]) < 60 for e in events)
        if not clash:
            events.append(ev)
    return events


def generate(seed: int = 42, end_date: str = "2026-09-25", n_days: int = C.N_DAYS,
             n_random_events: int = 24) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=end_date, periods=n_days, freq="D")
    markets, cats = list(C.MARKETS), list(C.CATEGORIES)

    # SKU master
    sku_rows = []
    for c in cats:
        spec = C.CATEGORIES[c]
        for i in range(1, C.SKUS_PER_CATEGORY + 1):
            price = round(float(rng.uniform(*spec["price"])), 2)
            margin = float(np.clip(spec["margin"] * rng.uniform(0.85, 1.15), 0.05, 0.85))
            sku_rows.append(dict(sku=f"{c[:3].upper()}-{i:03d}", category=c,
                                 unit_price=price, unit_cost=round(price * (1 - margin), 2)))
    skus = pd.DataFrame(sku_rows)
    cat_idx = skus["category"].map({c: i for i, c in enumerate(cats)}).to_numpy()

    # Base daily demand per market and SKU
    base = np.empty((len(markets), len(skus)))
    for s, row in skus.iterrows():
        lo, hi = C.CATEGORIES[row["category"]]["base"]
        for m, code in enumerate(markets):
            base[m, s] = rng.uniform(lo, hi) * C.MARKETS[code] * rng.uniform(0.8, 1.2)

    # Calendar effects
    dow = np.array(C.WEEKDAY_SHAPE)[dates.dayofweek.to_numpy()]
    doy = dates.dayofyear.to_numpy()
    annual = np.stack([_annual(doy, C.CATEGORIES[c]["amp"], C.CATEGORIES[c]["peak_day"]) for c in cats], axis=1)

    # Injected events -> multiplier cube (day, market, category)
    events = _pick_events(rng, n_days, n_random_events)
    mult = np.ones((n_days, len(markets), len(cats)))
    kind_cube = np.full((n_days, len(markets), len(cats)), -1)
    for e in events:
        m, c = markets.index(e["market"]), cats.index(e["category"])
        for k in range(e["duration"]):
            d = e["start"] + k
            if d >= n_days:
                break
            mult[d, m, c] = 1 + (e["multiplier"] - 1) * min(1.0, (k + 1) / e["ramp"])
            kind_cube[d, m, c] = C.EVENT_KINDS.index(e["kind"])

    lam_base = dow[:, None, None] * annual[:, cat_idx][:, None, :] * base[None, :, :]
    lam = lam_base * mult[:, :, cat_idx]
    units = rng.poisson(lam)

    # Modelled segment attribution (no extra random draws, so sales are unchanged by this block).
    def by_cat(a):
        return np.stack([a[:, :, cat_idx == ci].sum(axis=2) for ci in range(len(cats))], axis=2)

    b = np.array(C.SEGMENT_BASE_SHARE)
    u_by_kind = np.array([C.SEGMENT_UPLIFT_SHARE[k] for k in C.EVENT_KINDS])
    lam_b_cm, lam_cm, units_cm = by_cat(lam_base), by_cat(lam), by_cat(units)
    u = np.where(kind_cube[..., None] >= 0, u_by_kind[np.clip(kind_cube, 0, None)], b)
    share = (lam_b_cm[..., None] * b + (lam_cm - lam_b_cm)[..., None] * u) / lam_cm[..., None]
    seg_units = units_cm[..., None] * share
    n_s = len(C.SEGMENTS)
    segments = pd.DataFrame({
        "date": np.repeat(dates.to_numpy(), len(markets) * len(cats) * n_s),
        "market": np.tile(np.repeat(markets, len(cats) * n_s), n_days),
        "category": np.tile(np.repeat(cats, n_s), n_days * len(markets)),
        "segment": np.tile(C.SEGMENTS, n_days * len(markets) * len(cats)),
        "units": seg_units.reshape(-1).round(2),
    })

    sales = pd.DataFrame({
        "date": np.repeat(dates.to_numpy(), len(markets) * len(skus)),
        "market": np.tile(np.repeat(markets, len(skus)), n_days),
        "sku": np.tile(skus["sku"].to_numpy(), n_days * len(markets)),
        "units": units.reshape(-1),
    })
    sales["category"] = sales["sku"].str[:3].map({c[:3].upper(): c for c in cats})
    sales = sales[["date", "market", "sku", "category", "units"]]

    # Ground truth for the backtest: expected daily units with and without the injected events.
    baseline = pd.DataFrame({
        "date": np.repeat(dates.to_numpy(), len(markets) * len(cats)),
        "market": np.tile(np.repeat(markets, len(cats)), n_days),
        "category": np.tile(cats, n_days * len(markets)),
        "baseline_units": lam_b_cm.reshape(-1).round(2),
        "expected_units": lam_cm.reshape(-1).round(2),
    })

    # Inventory snapshot on the last data day
    lam0 = lam_base[-14:].mean(axis=0)  # (market, sku) baseline without events
    inv_rows = []
    for m, code in enumerate(markets):
        for s, row in skus.iterrows():
            cover = rng.uniform(9, 24)
            on_hand = int(round(lam0[m, s] * cover))
            committed = int(round(on_hand * rng.uniform(0.35, 0.60)))
            on_order = int(round(lam0[m, s] * rng.uniform(0, 14)))
            inv_rows.append(dict(market=code, dc=C.DC_OF[code], sku=row["sku"], category=row["category"],
                                 on_hand=on_hand, committed=committed, on_order=on_order,
                                 on_order_eta_days=int(rng.integers(10, 36))))
    inventory = pd.DataFrame(inv_rows)

    # Make the demo scenario reproducible: uncommitted Home stock in Market C covers 60% of the 14-day lift.
    m_demo = markets.index(C.DEMO_MARKET)
    mask = (inventory["market"] == C.DEMO_MARKET) & (inventory["category"] == C.DEMO_CATEGORY)
    for idx in inventory.index[mask]:
        s = int(skus.index[skus["sku"] == inventory.at[idx, "sku"]][0])
        lift14 = lam0[m_demo, s] * (C.DEMO_MULTIPLIER - 1) * 14
        inventory.at[idx, "on_hand"] = inventory.at[idx, "committed"] + int(round(C.DEMO_STOCK_COVER * lift14))

    sourcing_rows = []
    for c in cats:
        spec = C.CATEGORIES[c]
        sourcing_rows.append(dict(category=c, mode="sea", lead_days=spec["sea_days"],
                                  unit_cost_multiplier=1.0, min_order_units=2000, supplier=f"S-{c[:3].upper()}"))
        sourcing_rows.append(dict(category=c, mode="air", lead_days=spec["air_days"],
                                  unit_cost_multiplier=C.AIR_COST_MULTIPLIER, min_order_units=200,
                                  supplier=f"S-{c[:3].upper()}"))
    sourcing = pd.DataFrame(sourcing_rows)

    ev = pd.DataFrame(events)
    ev.insert(0, "event_id", [f"EV-{i:03d}" for i in range(len(ev))])
    ev["start_date"] = [dates[e["start"]].date().isoformat() for e in events]
    ev = ev.rename(columns={"duration": "duration_days", "ramp": "ramp_days"}).drop(columns="start")

    return dict(sales=sales, skus=skus, inventory=inventory, sourcing=sourcing, events=ev, segments=segments,
                baseline=baseline)


def write(tables: dict[str, pd.DataFrame], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    tables["sales"].to_csv(out / "sales.csv.gz", index=False)
    tables["segments"].to_csv(out / "segments.csv.gz", index=False)
    tables["baseline"].to_csv(out / "baseline.csv.gz", index=False)
    for name in ("skus", "inventory", "sourcing", "events"):
        tables[name].to_csv(out / f"{name}.csv", index=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="data/synthetic")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--end-date", default="2026-09-25")
    p.add_argument("--events", type=int, default=24)
    a = p.parse_args()
    tables = generate(seed=a.seed, end_date=a.end_date, n_random_events=a.events)
    write(tables, Path(a.out))
    print({k: len(v) for k, v in tables.items()}, "->", a.out)


if __name__ == "__main__":
    main()
