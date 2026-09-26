import json

import pytest

from aurelia import config as C
from aurelia.tools import TOOLS, dispatch


def test_every_tool_dispatches_and_is_json_serialisable(world):
    calls = {
        "get_sales_history": dict(market="C", category="home", days=30),
        "detect_demand_spikes": dict(),
        "get_inventory_position": dict(market="C", category="home"),
        "get_sourcing_options": dict(category="home", units_needed=2500),
        "get_margin": dict(market="C", category="home"),
        "get_segment_mix": dict(market="C", category="home"),
    }
    assert set(calls) == {t["name"] for t in TOOLS}
    for name, args in calls.items():
        json.dumps(dispatch(world, name, args))


def test_inventory_reflects_demo_scenario(world):
    inv = dispatch(world, "get_inventory_position", dict(market=C.DEMO_MARKET, category=C.DEMO_CATEGORY))
    assert inv["uncommitted"] == inv["on_hand"] - inv["committed"] > 0


def test_sourcing_air_is_faster_and_costlier(world):
    sea, air = None, None
    opts = dispatch(world, "get_sourcing_options", dict(category="home", units_needed=2500))
    air, sea = opts[0], opts[1]
    assert (air["mode"], sea["mode"]) == ("air", "sea")
    assert air["lead_days"] < sea["lead_days"]
    assert air["estimated_cost_eur"] > sea["estimated_cost_eur"]


def test_bad_input_gives_readable_error(world):
    with pytest.raises(ValueError, match="unknown market"):
        dispatch(world, "get_margin", dict(market="Z", category="home"))
    with pytest.raises(ValueError, match="unknown tool"):
        dispatch(world, "nope")
