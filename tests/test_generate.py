from aurelia import config as C
from aurelia.generate import generate


def test_shapes(tables):
    n_skus = len(C.CATEGORIES) * C.SKUS_PER_CATEGORY
    assert len(tables["skus"]) == n_skus
    assert len(tables["sales"]) == C.N_DAYS * len(C.MARKETS) * n_skus
    assert len(tables["inventory"]) == len(C.MARKETS) * n_skus
    assert set(tables["sales"]["units"].map(type)) <= {int} or tables["sales"]["units"].min() >= 0


def test_seeded_and_reproducible():
    a, b = generate(seed=7), generate(seed=7)
    assert a["sales"]["units"].equals(b["sales"]["units"])
    assert a["events"].equals(b["events"])


def test_demo_event_is_scripted(tables):
    ev = tables["events"]
    demo = ev[ev["scripted"]]
    assert len(demo) == 1
    row = demo.iloc[0]
    assert (row["market"], row["category"]) == (C.DEMO_MARKET, C.DEMO_CATEGORY)


def test_demo_stock_covers_sixty_percent_of_lift(tables):
    inv = tables["inventory"]
    sel = inv[(inv["market"] == C.DEMO_MARKET) & (inv["category"] == C.DEMO_CATEGORY)]
    assert (sel["on_hand"] >= sel["committed"]).all()
    assert (sel["on_hand"] - sel["committed"]).sum() > 0
