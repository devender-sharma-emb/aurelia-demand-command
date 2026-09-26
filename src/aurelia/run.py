"""Run the orchestrator from the command line.

  python -m aurelia.run --market C --category home                  # offline stand-in, no API key
  python -m aurelia.run --market C --category home --live           # Claude via ANTHROPIC_API_KEY
  python -m aurelia.run --market C --category home --budget 60000 --approve "J. Doe"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import AuditLog
from .generate import generate
from .llm import AnthropicClient, OfflineClient
from .orchestrator import ApprovalRequired, Blocked, DemandOrchestrator
from .world import RetailWorld


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data/synthetic")
    p.add_argument("--market", default="C")
    p.add_argument("--category", default="home")
    p.add_argument("--budget", type=float, default=40_000)
    p.add_argument("--live", action="store_true", help="use Claude instead of the offline stand-in")
    p.add_argument("--approve", metavar="NAME", help="approve the plan on behalf of NAME if approval is needed")
    p.add_argument("--audit", default="data/audit.jsonl")
    a = p.parse_args()

    world = RetailWorld.from_dir(a.data) if Path(a.data, "sales.csv.gz").exists() else RetailWorld(**generate())
    audit = AuditLog(a.audit)
    orch = DemandOrchestrator(world, AnthropicClient() if a.live else OfflineClient(), audit)

    plan = orch.analyze(a.market, a.category, a.budget)
    for s in plan["steps"]:
        print(f"[{s['agent']}] {s['summary']}")
        for c in s.get("corrections", []):
            print(f"    corrected: {c}")
    if plan["decision"]:
        print(json.dumps({k: plan["decision"][k] for k in (
            "coverage", "campaign_scale", "spend_approved_eur", "freed_budget_eur", "reallocation",
            "replenishment", "tier")}, indent=2))
    print("status:", plan["status"])
    if plan["status"] in ("ready", "needs_approval", "blocked"):
        try:
            print(json.dumps(orch.execute(plan, approved_by=a.approve), indent=2))
        except (ApprovalRequired, Blocked) as exc:
            print(f"not executed: {exc}")
    print(f"audit trail: {len(audit.entries)} entries in {a.audit}")


if __name__ == "__main__":
    main()
