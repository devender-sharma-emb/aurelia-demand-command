import json

import pytest

from aurelia import config as C
from aurelia.audit import AuditLog
from aurelia.llm import LLMResponse, OfflineClient
from aurelia.orchestrator import ApprovalRequired, Blocked, DemandOrchestrator


def _orch(world, client=None, audit=None):
    return DemandOrchestrator(world, client or OfflineClient(), audit or AuditLog())


def test_demo_scenario_end_to_end_auto_execute(world):
    audit = AuditLog()
    orch = _orch(world, audit=audit)
    plan = orch.analyze(C.DEMO_MARKET, C.DEMO_CATEGORY)
    d = plan["decision"]
    assert plan["status"] == "ready" and d["tier"] == "auto_execute"
    assert 0.5 < d["coverage"] < 0.85
    assert d["campaign_scale"] == pytest.approx(min(1.0, d["coverage"] / C.LIFT_SIZING_FACTOR), abs=1e-3)
    assert plan["segment_mix"]["value_seeking_share_of_uplift"] > 0.6
    assert [s["agent"] for s in plan["steps"]] == ["sensing", "segmentation", "orchestrator", "campaign", "creative"]

    out = orch.execute(plan)
    assert out["status"] == "executed"
    assert out["allocation"]["status"] == "accepted"
    assert out["replenishment"]["status"] == "accepted" and out["replenishment"]["mode"] == "air"
    events = [e["event"] for e in audit.entries]
    for needed in ("analysis_start", "decision", "allocation_request", "replenishment_request",
                   "measurement_planned", "executed"):
        assert needed in events
    assert [e["seq"] for e in audit.entries] == list(range(1, len(audit.entries) + 1))


def test_large_budget_needs_human_approval_and_nothing_is_sent_before_it(world, monkeypatch):
    monkeypatch.setattr(C, "APPROVAL_LIMIT_EUR", 5_000)
    audit = AuditLog()
    orch = _orch(world, audit=audit)
    plan = orch.analyze(C.DEMO_MARKET, C.DEMO_CATEGORY, budget=60_000)
    assert plan["status"] == "needs_approval"
    with pytest.raises(ApprovalRequired):
        orch.execute(plan)
    assert not audit.events("allocation_request") and not audit.events("replenishment_request")

    out = orch.execute(plan, approved_by="Devvender")
    assert out["approved_by"] == "Devvender"
    grant = audit.events("approval_granted")[0]
    assert grant["actor"] == "human" and grant["data"]["approved_by"] == "Devvender"


def test_budget_over_cap_is_blocked(world):
    orch = _orch(world)
    plan = orch.analyze(C.DEMO_MARKET, C.DEMO_CATEGORY, budget=C.BUDGET_CAP_EUR + 5_000)
    assert plan["status"] == "blocked" and plan["campaign"] is None
    with pytest.raises(Blocked):
        orch.execute(plan, approved_by="anyone")


def test_no_spike_means_no_action(world):
    audit = AuditLog()
    plan = _orch(world, audit=audit).analyze("A", "jewelry")
    assert plan["status"] == "no_spike" and plan["decision"] is None
    assert not audit.events("decision")


class BadCreativeClient(OfflineClient):
    """Stand-in that misbehaves: unsafe campaign and banned creative claims."""
    def create(self, system, messages, tools):
        if "[agent:campaign]" in system:
            return LLMResponse([{"type": "text", "text": json.dumps(dict(
                channel_mix=dict(paid_search=50, tiktok=50), offer_type="mystery", promo_depth_pct=90))}], "end_turn")
        if "[agent:creative]" in system:
            return LLMResponse([{"type": "text", "text": json.dumps(dict(
                headline="The cheapest deals, guaranteed", body="x"))}], "end_turn")
        return super().create(system, messages, tools)


def test_unsafe_llm_output_is_corrected_or_stops_execution(world):
    audit = AuditLog()
    orch = _orch(world, BadCreativeClient(), audit)
    plan = orch.analyze(C.DEMO_MARKET, C.DEMO_CATEGORY)
    assert plan["campaign"]["promo_depth_pct"] <= 40 and plan["campaign"]["offer_type"] in C.OFFER_TYPES
    assert set(plan["campaign"]["channel_mix"]) <= set(C.CHANNELS)
    assert audit.events("campaign_corrected") and audit.events("creative_rejected")
    with pytest.raises(Blocked, match="creative"):
        orch.execute(plan)
    assert not audit.events("allocation_request")


def test_money_numbers_come_from_tools_not_from_model_text(world):
    class Liar(OfflineClient):
        def create(self, system, messages, tools):
            r = super().create(system, messages, tools)
            if "[agent:sensing]" in system and r.stop_reason == "end_turn":
                return LLMResponse([{"type": "text", "text": json.dumps(dict(
                    spike_confirmed=True, summary="Projected +999999 units", confidence="high",
                    likely_driver="x"))}], "end_turn")
            return r
    plan = _orch(world, Liar()).analyze(C.DEMO_MARKET, C.DEMO_CATEGORY)
    assert plan["decision"]["projected_lift_units"] == plan["spike"]["projected_incremental_14d"] < 20_000
