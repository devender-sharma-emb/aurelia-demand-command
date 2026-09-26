"""Read-only view of the synthetic Aurelia world. Every method returns plain JSON-friendly data,
so the same functions can be exposed to Claude as tools (see tools.py)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config as C
from .detect import active_spike, find_spikes


class RetailWorld:
    def __init__(self, sales: pd.DataFrame, skus: pd.DataFrame, inventory: pd.DataFrame,
                 sourcing: pd.DataFrame, events: pd.DataFrame):
        self.sales = sales.assign(date=pd.to_datetime(sales["date"]))
        self.skus, self.inventory, self.sourcing, self.events = skus, inventory, sourcing, events
        self._series: dict[tuple[str, str], pd.Series] = {}

    @classmethod
    def from_dir(cls, path: str | Path) -> "RetailWorld":
        p = Path(path)
        return cls(pd.read_csv(p / "sales.csv.gz"), pd.read_csv(p / "skus.csv"),
                   pd.read_csv(p / "inventory.csv"), pd.read_csv(p / "sourcing.csv"),
                   pd.read_csv(p / "events.csv"))

    @property
    def as_of(self) -> pd.Timestamp:
        return self.sales["date"].max()

    def _check(self, market: str | None = None, category: str | None = None) -> None:
        if market is not None and market not in C.MARKETS:
            raise ValueError(f"unknown market {market!r}; valid: {sorted(C.MARKETS)}")
        if category is not None and category not in C.CATEGORIES:
            raise ValueError(f"unknown category {category!r}; valid: {sorted(C.CATEGORIES)}")

    def series(self, market: str, category: str) -> pd.Series:
        self._check(market, category)
        key = (market, category)
        if key not in self._series:
            sel = self.sales[(self.sales["market"] == market) & (self.sales["category"] == category)]
            self._series[key] = sel.groupby("date")["units"].sum().asfreq("D")
        return self._series[key]

    # ---- tool implementations -------------------------------------------------------------

    def sales_history(self, market: str, category: str, days: int = 90) -> dict:
        s = self.series(market, category).tail(max(1, min(int(days), 730)))
        return dict(market=market, category=category, as_of=str(self.as_of.date()),
                    daily=[dict(date=str(d.date()), units=int(u)) for d, u in s.items()])

    def inventory_position(self, market: str, category: str) -> dict:
        self._check(market, category)
        inv = self.inventory[(self.inventory["market"] == market) & (self.inventory["category"] == category)]
        on_hand, committed = int(inv["on_hand"].sum()), int(inv["committed"].sum())
        recent = float(self.series(market, category).tail(28).mean())
        return dict(market=market, category=category, dc=C.DC_OF[market], as_of=str(self.as_of.date()),
                    on_hand=on_hand, committed=committed, uncommitted=on_hand - committed,
                    on_order=int(inv["on_order"].sum()),
                    on_order_eta_days=int(round(float(inv["on_order_eta_days"].mean()))),
                    avg_daily_units_28d=round(recent, 1))

    def sourcing_options(self, category: str, units_needed: int) -> list[dict]:
        self._check(category=category)
        avg_cost = float(self.skus[self.skus["category"] == category]["unit_cost"].mean())
        out = []
        for _, r in self.sourcing[self.sourcing["category"] == category].iterrows():
            cost = units_needed * avg_cost * float(r["unit_cost_multiplier"])
            out.append(dict(category=category, mode=r["mode"], supplier=r["supplier"],
                            lead_days=int(r["lead_days"]), min_order_units=int(r["min_order_units"]),
                            meets_minimum=units_needed >= int(r["min_order_units"]),
                            estimated_cost_eur=round(cost, 2)))
        return sorted(out, key=lambda o: o["lead_days"])

    def margin(self, market: str, category: str) -> dict:
        self._check(market, category)
        recent = self.sales[(self.sales["market"] == market) & (self.sales["category"] == category)
                            & (self.sales["date"] > self.as_of - pd.Timedelta(days=28))]
        mix = recent.groupby("sku")["units"].sum().rename("units").reset_index().merge(self.skus, on="sku")
        w = mix["units"].sum() or 1
        price = float((mix["unit_price"] * mix["units"]).sum() / w)
        cost = float((mix["unit_cost"] * mix["units"]).sum() / w)
        return dict(market=market, category=category, avg_unit_price_eur=round(price, 2),
                    avg_unit_cost_eur=round(cost, 2), margin_per_unit_eur=round(price - cost, 2),
                    margin_pct=round(100 * (price - cost) / price, 1))

    def detect_spikes(self, market: str | None = None, category: str | None = None) -> list[dict]:
        self._check(market, category)
        out = []
        for m in ([market] if market else list(C.MARKETS)):
            for c in ([category] if category else list(C.CATEGORIES)):
                sp = active_spike(self.series(m, c))
                if sp:
                    out.append(dict(market=m, category=c, start=str(sp["start"].date()),
                                    end=str(sp["end"].date()), days_active=sp["days"],
                                    uplift_ratio=round(sp["uplift_ratio"], 2), peak_z=round(sp["peak_z"], 1),
                                    incremental_per_day=round(sp["incremental_per_day"], 1),
                                    projected_incremental_14d=sp["projected_incremental_14d"],
                                    projection_basis=sp["projection_basis"]))
        return sorted(out, key=lambda r: -r["projected_incremental_14d"])

    def historical_spikes(self, market: str, category: str) -> list[dict]:
        return find_spikes(self.series(market, category))
