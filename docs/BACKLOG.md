# Backlog

## Week 1: foundation (done in this commit)

- [x] Project scaffold, tests, README
- [x] Seeded synthetic dataset with ground-truth events
- [x] Tool functions and Claude tool schemas
- [x] Spike detection with recall and false-alarm tests
- [x] Draft hand-off contracts (`docs/INTERFACES.md`)
- [ ] Review the contracts with the Merchandising and Sourcing teams
- [ ] Ask the mentor which Capgemini accelerators to use (deck slide 7)

## Week 2: agents and orchestrator

- [ ] Add the `anthropic` SDK and a small agent loop with tool use
- [ ] Sensing Agent: confirm and size the spike using the tools
- [ ] Segmentation Agent: split the uplift by customer segment (needs a synthetic segment table)
- [ ] Campaign and Promo Agents: propose channel mix, budget and offer depth within a margin floor
- [ ] Orchestrator: check stock and sourcing before approving spend, scale the campaign to stock,
      reallocate freed budget to a surplus category
- [ ] Guardrails: margin floor, budget cap, autonomy tiers (auto-execute, approval above EUR 15k)
- [ ] Approval gate and audit log (one JSON line per decision, with the tool calls behind it)
- [ ] Merchandising and Sourcing stubs that implement `docs/INTERFACES.md`
- [ ] Measurement Agent: holdout test design
- [ ] Creative and Localization Agent: lightweight version

## Week 3: proof and packaging

- [ ] Backtest harness: run "campaign alone" and "with orchestrator" on many injected events
- [ ] Replace the illustrative KPIs in the deck with backtest results (margin, lost demand, wasted spend,
      markdown units)
- [ ] Connect the dashboard to the live backend
- [ ] Re-record the demo, update the deck and the voiceover
- [ ] Fill in the Capgemini asset mapping

## Risks

- Backtest numbers are only as good as the synthetic assumptions. State them next to every result.
- LLM agents are non-deterministic. Keep decisions that involve money in plain code and use Claude
  for reasoning, explanation and tool selection, with the audit log as the source of truth.
