"""Spike detection on a daily demand series.

Baseline for each day is the median of the same weekday over the previous four weeks.
A day is flagged when it is both statistically and materially above that baseline.
A spike is a run of consecutive flagged days.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = (7, 14, 21, 28)


def score(series: pd.Series) -> pd.DataFrame:
    """Return expected, residual, z-score and ratio per day."""
    x = series.astype(float)
    expected = pd.concat([x.shift(k) for k in LAGS], axis=1).median(axis=1)
    resid = x - expected
    scale = 1.4826 * resid.abs().shift(1).rolling(90, min_periods=28).median()
    scale = np.maximum(scale, 0.02 * expected)
    return pd.DataFrame({"actual": x, "expected": expected, "resid": resid,
                         "z": resid / scale, "ratio": x / expected})


def find_spikes(series: pd.Series, z_min: float = 3.0, ratio_min: float = 1.25,
                min_run: int = 3) -> list[dict]:
    """All runs of at least `min_run` consecutive flagged days."""
    s = score(series)
    flag = ((s["z"] > z_min) & (s["ratio"] > ratio_min)).fillna(False).to_numpy()
    out, i, n = [], 0, len(flag)
    while i < n:
        if not flag[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flag[j + 1]:
            j += 1
        if j - i + 1 >= min_run:
            run = s.iloc[i:j + 1]
            out.append(dict(start=run.index[0], end=run.index[-1], days=j - i + 1,
                            uplift_ratio=float(run["ratio"].mean()), peak_z=float(run["z"].max()),
                            incremental_per_day=float(run["resid"].tail(3).mean())))
        i = j + 1
    return out


def active_spike(series: pd.Series, **kw) -> dict | None:
    """The spike still running on the last day (or ended the day before), if any."""
    last = series.index[-1]
    for sp in reversed(find_spikes(series, **kw)):
        if (last - sp["end"]).days <= 1:
            sp = dict(sp)
            sp["projected_incremental_14d"] = int(round(max(sp["incremental_per_day"], 0) * 14))
            sp["projection_basis"] = "naive persistence of the last 3 days of uplift"
            return sp
    return None
