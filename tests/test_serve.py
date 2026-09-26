import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from aurelia import config as C
from aurelia.serve import App, handler


@pytest.fixture()
def server(world, monkeypatch):
    monkeypatch.setattr(C, "APPROVAL_LIMIT_EUR", 5_000)
    app = App(world, live=False, backtest=Path("docs/results/backtest_summary.json"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_state_lists_the_demo_spike(server):
    code, s = call(server + "/api/state")
    assert code == 200 and (s["spikes"][0]["market"], s["spikes"][0]["category"]) == ("C", "home")
    assert "not a language model" in s["agents"]


def test_analyze_then_approval_flow(server):
    code, plan = call(server + "/api/analyze", dict(market="C", category="home", budget=40000))
    assert code == 200 and plan["status"] == "needs_approval"
    code, err = call(server + "/api/execute", dict(plan_id=plan["plan_id"]))
    assert code == 409 and err["code"] == "approval_required"
    code, out = call(server + "/api/execute", dict(plan_id=plan["plan_id"], approved_by="Devvender"))
    assert code == 200 and out["status"] == "executed" and out["approved_by"] == "Devvender"
    _, audit = call(server + "/api/audit")
    assert any(e["event"] == "approval_granted" for e in audit)


def test_bad_input_is_a_400_and_unknown_plan_a_404(server):
    assert call(server + "/api/analyze", dict(market="Z", category="home"))[0] == 400
    assert call(server + "/api/analyze", dict(market="C", category="home", budget=-5))[0] == 400
    assert call(server + "/api/execute", dict(plan_id="PL-9999"))[0] == 404
    assert call(server + "/api/nope")[0] == 404


def test_backtest_summary_is_served(server):
    code, s = call(server + "/api/backtest")
    assert code == 200 and s["setup"]["n_seeds"] == 20
