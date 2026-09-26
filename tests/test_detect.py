import pandas as pd

from aurelia import config as C


def _overlaps(spike, start, duration, slack=3):
    lo = pd.Timestamp(start)
    hi = lo + pd.Timedelta(days=duration + slack)
    return spike["start"] <= hi and spike["end"] >= lo


def test_recall_and_false_alarms(world):
    ev = world.events[~world.events["scripted"]]
    hits = 0
    for _, e in ev.iterrows():
        spikes = world.historical_spikes(e["market"], e["category"])
        hits += any(_overlaps(s, e["start_date"], e["duration_days"]) for s in spikes)
    assert hits / len(ev) >= 0.9, f"recall {hits}/{len(ev)}"

    # False alarms: spikes in series that have no injected event nearby.
    false_alarms = 0
    for m in C.MARKETS:
        for c in C.CATEGORIES:
            mine = world.events[(world.events["market"] == m) & (world.events["category"] == c)]
            for s in world.historical_spikes(m, c):
                if not any(_overlaps(s, e["start_date"], e["duration_days"]) for _, e in mine.iterrows()):
                    false_alarms += 1
    assert false_alarms <= 2, f"{false_alarms} false alarms across {len(C.MARKETS) * len(C.CATEGORIES)} series"


def test_demo_spike_is_active_and_correct(world):
    found = world.detect_spikes(C.DEMO_MARKET, C.DEMO_CATEGORY)
    assert len(found) == 1
    sp = found[0]
    assert sp["uplift_ratio"] > 1.25
    assert sp["projected_incremental_14d"] > 0
    assert 2 <= sp["days_active"] <= C.DEMO_DAYS_AGO


def test_quiet_series_has_no_active_spike(world):
    active = {(s["market"], s["category"]) for s in world.detect_spikes()}
    assert (C.DEMO_MARKET, C.DEMO_CATEGORY) in active
    assert len(active) <= 3
