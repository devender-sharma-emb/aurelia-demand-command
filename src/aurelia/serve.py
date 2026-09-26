"""Local server for the dashboard. Standard library only.

  python -m aurelia.serve                      # http://127.0.0.1:8000, offline stand-in agents
  python -m aurelia.serve --live               # Claude agents via ANTHROPIC_API_KEY
  python -m aurelia.serve --approval-limit 5000   # make the human approval step easy to show

Demo grade: there is no authentication, so the approver name is typed in and only recorded.
A real deployment needs single sign-on and an authorization check on /api/execute.
"""
from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config as C
from .audit import AuditLog
from .generate import generate
from .llm import DEFAULT_MODEL, AnthropicClient, OfflineClient
from .orchestrator import ApprovalRequired, Blocked, DemandOrchestrator
from .world import RetailWorld

PAGE = Path(__file__).parent / "dashboard" / "index.html"
MAX_BODY = 64 * 1024


class App:
    def __init__(self, world: RetailWorld, live: bool, backtest: Path | None):
        self.world, self.live, self.backtest = world, live, backtest
        self.audit = AuditLog()
        client = AnthropicClient() if live else OfflineClient()
        self.orch = DemandOrchestrator(world, client, self.audit)
        self.plans: dict[str, dict] = {}
        self.lock = threading.Lock()

    def state(self) -> dict:
        return dict(as_of=str(self.world.as_of.date()), markets=sorted(C.MARKETS), categories=sorted(C.CATEGORIES),
                    spikes=self.world.detect_spikes(), default_budget=C.DEFAULT_BUDGET_EUR,
                    limits=dict(budget_cap=C.BUDGET_CAP_EUR, approval=C.APPROVAL_LIMIT_EUR, margin_floor=C.MARGIN_FLOOR_PCT),
                    agents="Claude (" + DEFAULT_MODEL + ")" if self.live else "offline stand-in, not a language model")

    def analyze(self, body: dict) -> dict:
        market, category = str(body.get("market")), str(body.get("category"))
        if market not in C.MARKETS or category not in C.CATEGORIES:
            raise ValueError(f"unknown market or category: {market!r}, {category!r}")
        budget = float(body.get("budget", C.DEFAULT_BUDGET_EUR))
        if not 0 < budget <= 1_000_000:
            raise ValueError("budget must be between 0 and 1,000,000")
        with self.lock:
            plan = self.orch.analyze(market, category, budget)
            self.plans[plan["plan_id"]] = plan
            return plan

    def execute(self, body: dict) -> tuple[int, dict]:
        with self.lock:
            plan = self.plans.get(str(body.get("plan_id")))
            if plan is None:
                return 404, dict(error="unknown plan_id")
            by = (str(body.get("approved_by") or "").strip()[:80]) or None
            try:
                return 200, self.orch.execute(plan, approved_by=by)
            except ApprovalRequired as e:
                return 409, dict(error=str(e), code="approval_required")
            except Blocked as e:
                return 403, dict(error=str(e), code="blocked")

    def backtest_summary(self):
        if self.backtest and self.backtest.exists():
            return json.loads(self.backtest.read_text())
        return None


def handler(app: App):
    class H(BaseHTTPRequestHandler):
        def _send(self, code: int, payload, ctype: str = "application/json") -> None:
            data = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if self.path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if self.path == "/api/state":
                return self._send(200, app.state())
            if self.path == "/api/backtest":
                return self._send(200, app.backtest_summary())
            if self.path == "/api/audit":
                return self._send(200, app.audit.entries[-60:])
            self._send(404, dict(error="not found"))

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, dict(error="body too large"))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("body must be a JSON object")
                if self.path == "/api/analyze":
                    return self._send(200, app.analyze(body))
                if self.path == "/api/execute":
                    code, out = app.execute(body)
                    return self._send(code, out)
                self._send(404, dict(error="not found"))
            except (ValueError, KeyError, TypeError) as e:
                self._send(400, dict(error=f"{type(e).__name__}: {e}"))

        def log_message(self, *a):  # quiet
            pass
    return H


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data/synthetic")
    p.add_argument("--backtest", default="docs/results/backtest_summary.json")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--live", action="store_true")
    p.add_argument("--approval-limit", type=float)
    a = p.parse_args()
    if a.approval_limit is not None:
        C.APPROVAL_LIMIT_EUR = a.approval_limit
    world = RetailWorld.from_dir(a.data) if Path(a.data, "sales.csv.gz").exists() else RetailWorld(**generate())
    app = App(world, a.live, Path(a.backtest))
    print(f"Demand Command dashboard on http://{a.host}:{a.port}  (agents: {app.state()['agents']})")
    ThreadingHTTPServer((a.host, a.port), handler(app)).serve_forever()


if __name__ == "__main__":
    main()
