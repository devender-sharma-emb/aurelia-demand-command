"""Demand Orchestrator: no campaign without stock to serve it.

analyze() runs the agents and produces a plan without touching any other team's system.
execute() sends the requests to Merchandising and Sourcing, and only after the tier allows it.
"""
from __future__ import annotations

import itertools

from . import config as C
from .agent import run_agent
from .agents import AGENTS, tool_defs
from .audit import AuditLog
from .decision import max_promo_depth_pct, plan_campaign, validate_campaign, validate_creative
from .llm import LLMClient
from .stubs import MerchandisingStub, SourcingStub
from .tools import dispatch
from .world import RetailWorld


class ApprovalRequired(RuntimeError):
    pass


class Blocked(RuntimeError):
    pass


class DemandOrchestrator:
    def __init__(self, world: RetailWorld, client: LLMClient, audit: AuditLog | None = None):
        self.world, self.client = world, client
        self.audit = audit or AuditLog()
        self.merch, self.sourcing = MerchandisingStub(world), SourcingStub(world)
        self._ids = itertools.count(1)

    # ---- helpers --------------------------------------------------------------------------

    def _agent(self, name: str, task: dict):
        return run_agent(self.client, name, AGENTS[name]["system"], task, tool_defs(name),
                         lambda n, a: dispatch(self.world, n, a), self.audit)

    def _tool(self, name: str, **args):
        out = dispatch(self.world, name, args)
        self.audit.log("orchestrator", "tool_call", dict(name=name, input=args, is_error=False))
        return out

    # ---- analysis -------------------------------------------------------------------------

    def analyze(self, market: str, category: str, budget: float = C.DEFAULT_BUDGET_EUR) -> dict:
        plan_id = f"PL-{next(self._ids):04d}"
        steps: list[dict] = []
        self.audit.log("orchestrator", "analysis_start", dict(plan_id=plan_id, market=market, category=category,
                                                             budget_eur=budget))

        sensing = self._agent("sensing", dict(market=market, category=category))
        spikes = sensing.tool_result("detect_demand_spikes") or []
        spike = next((s for s in spikes if s["market"] == market and s["category"] == category), None)
        steps.append(dict(agent="sensing", summary=(sensing.output or {}).get("summary", sensing.final_text)))
        if spike is None:
            self.audit.log("orchestrator", "no_action", dict(plan_id=plan_id, reason="no active spike"))
            return dict(plan_id=plan_id, status="no_spike", steps=steps, decision=None)

        seg = self._agent("segmentation", dict(market=market, category=category))
        mix = seg.tool_result("get_segment_mix") or {}
        steps.append(dict(agent="segmentation", summary=(seg.output or {}).get("summary", seg.final_text),
                          value_seeking_share=mix.get("value_seeking_share_of_uplift")))

        inventory = self._tool("get_inventory_position", market=market, category=category)
        margin = self._tool("get_margin", market=market, category=category)
        others = [self._tool("get_inventory_position", market=market, category=c)
                  for c in C.CATEGORIES if c != category]
        decision = plan_campaign(spike=spike, inventory=inventory, margin=margin, other_inventory=others,
                                 get_sourcing=lambda n: self._tool("get_sourcing_options", category=category,
                                                                   units_needed=n), budget=budget)
        steps.append(dict(agent="orchestrator",
                          summary=(f"Stock covers {decision['coverage']:.0%} of the projected lift "
                                   f"({decision['supply_in_horizon_units']} of {decision['projected_lift_units']} units). "
                                   f"Spend EUR {decision['spend_approved_eur']:,} of EUR {decision['budget_requested_eur']:,}.")))
        self.audit.log("orchestrator", "decision", dict(plan_id=plan_id, **decision))

        campaign = creative = None
        if decision["tier"] != "blocked":
            depth = max_promo_depth_pct(margin["margin_pct"])
            run = self._agent("campaign", dict(
                market=market, category=category, spend_eur=decision["spend_approved_eur"],
                segment_hint=(seg.output or {}).get("recommended_offer_style"),
                limits=dict(channels=C.CHANNELS, offer_types=C.OFFER_TYPES, max_promo_depth_pct=depth)))
            campaign, issues = validate_campaign(run.output, depth)
            steps.append(dict(agent="campaign", summary=campaign["rationale"] or "no rationale given", corrections=issues))
            if issues:
                self.audit.log("orchestrator", "campaign_corrected", dict(plan_id=plan_id, issues=issues))
            cr = self._agent("creative", dict(market=market, category=category, offer_type=campaign["offer_type"],
                                              promo_depth_pct=campaign["promo_depth_pct"]))
            creative, c_issues = validate_creative(cr.output)
            steps.append(dict(agent="creative", summary=creative["headline"], corrections=c_issues))
            if c_issues:
                self.audit.log("orchestrator", "creative_rejected", dict(plan_id=plan_id, issues=c_issues))

        status = {"blocked": "blocked", "needs_approval": "needs_approval", "auto_execute": "ready"}[decision["tier"]]
        return dict(plan_id=plan_id, status=status, steps=steps, decision=decision, campaign=campaign,
                    creative=creative, spike=spike, segment_mix=mix)

    # ---- execution ------------------------------------------------------------------------

    def execute(self, plan: dict, approved_by: str | None = None) -> dict:
        d = plan["decision"]
        if plan["status"] == "blocked":
            self.audit.log("orchestrator", "execution_refused", dict(plan_id=plan["plan_id"], reasons=d["blocked_reasons"]))
            raise Blocked("; ".join(d["blocked_reasons"]))
        if plan["status"] == "needs_approval":
            if not approved_by:
                self.audit.log("orchestrator", "approval_pending", dict(plan_id=plan["plan_id"],
                                                                        change_eur=d["freed_budget_eur"]))
                raise ApprovalRequired(f"budget change of EUR {d['freed_budget_eur']:,} needs human approval")
            self.audit.log("human", "approval_granted", dict(plan_id=plan["plan_id"], approved_by=approved_by,
                                                            change_eur=d["freed_budget_eur"]))
        if plan.get("creative") and not plan["creative"]["approved"]:
            self.audit.log("orchestrator", "execution_refused", dict(plan_id=plan["plan_id"], reasons=["creative rejected"]))
            raise Blocked("creative copy failed brand guardrails; regenerate before executing")

        n = plan["plan_id"].split("-")[1]
        alloc_req = dict(request_id=f"AR-{n}", type="allocation_request", market=d["market"], category=d["category"],
                         reason="demand spike", units_requested=d["allocation_units"], horizon_days=d["horizon_days"],
                         units_available_uncommitted=d["uncommitted_units"], campaign_scale=d["campaign_scale"])
        alloc = self.merch.allocate(alloc_req)
        self.audit.log("orchestrator", "allocation_request", dict(request=alloc_req, response=alloc))

        replen_req = replen = None
        if d["replenishment"]:
            r = d["replenishment"]
            replen_req = dict(request_id=f"RR-{n}", type="replenishment_request", category=d["category"],
                              market=d["market"], units_requested=r["units"], needed_by_days=d["horizon_days"],
                              preferred_mode=r["mode"])
            replen = self.sourcing.replenish(replen_req)
            self.audit.log("orchestrator", "replenishment_request", dict(request=replen_req, response=replen))

        measurement = dict(holdout_pct=10, metric="incremental units and margin vs holdout",
                           duration_days=d["horizon_days"], market=d["market"], category=d["category"])
        self.audit.log("orchestrator", "measurement_planned", measurement)
        self.audit.log("orchestrator", "executed", dict(plan_id=plan["plan_id"], approved_by=approved_by))
        return dict(plan_id=plan["plan_id"], status="executed", allocation=alloc, replenishment=replen,
                    measurement=measurement, approved_by=approved_by)
