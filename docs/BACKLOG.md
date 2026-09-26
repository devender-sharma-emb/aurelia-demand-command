# Backlog

## Week 1: foundation (done in this commit)

- [x] Project scaffold, tests, README
- [x] Seeded synthetic dataset with ground-truth events
- [x] Tool functions and Claude tool schemas
- [x] Spike detection with recall and false-alarm tests
- [x] Draft hand-off contracts (`docs/INTERFACES.md`)
- [ ] Review the contracts with the Merchandising and Sourcing teams
- [ ] Ask the mentor which Capgemini accelerators to use (deck slide 7)

## Week 2: agents and orchestrator (done in this commit)

- [x] Add the `anthropic` SDK and a small agent loop with tool use
- [x] Sensing Agent: confirm and size the spike using the tools
- [x] Segmentation Agent: split the uplift by customer segment (needs a synthetic segment table)
- [x] Campaign and Promo Agents: propose channel mix, budget and offer depth within a margin floor
- [x] Orchestrator: check stock and sourcing before approving spend, scale the campaign to stock,
      reallocate freed budget to a surplus category
- [x] Guardrails: margin floor, budget cap, autonomy tiers (auto-execute, approval above EUR 15k)
- [x] Approval gate and audit log (one JSON line per decision, with the tool calls behind it)
- [x] Merchandising and Sourcing stubs that implement `docs/INTERFACES.md`
- [~] Measurement Agent: holdout test is planned at execution (10% holdout); analysis of results comes with the week 3 backtest
- [x] Creative and Localization Agent: lightweight version
- [ ] Run `--live` once with a real ANTHROPIC_API_KEY and record the transcript (not possible from the build environment)

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
