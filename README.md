# Aurelia Demand Command

Agentic AI for the **Marketing & Demand** value stream of Aurelia Retail Group (ARchithon 2026).
The system senses a demand spike, checks whether stock and sourcing can support it, scales the
campaign to what the supply chain can deliver, and hands allocation and replenishment requests to
Merchandising and Sourcing.

Everything here runs on **synthetic data**. Nothing in this repository is real Aurelia data.

## Status

| Piece | State |
|---|---|
| Synthetic dataset generator (8 markets, 5 categories, 60 SKUs, 2 years, 24 injected events plus one scripted demo event) | done |
| Tool functions and Claude tool schemas (`tools.py`) | done |
| Spike detection (same-weekday robust baseline) | done, tested |
| Four LLM agents (Sensing, Segmentation, Campaign/Promo, Creative) with least-privilege tools | done, live Claude path not yet run against the API |
| Orchestrator, stock guardrail, approval gate, audit log | done, tested |
| Merchandising and Sourcing stubs (`docs/INTERFACES.md`) | done |
| Backtest and live dashboard | week 3 |

## Quickstart

```bash
pip install -e ".[dev]"          # add ,live to install the Anthropic SDK
python -m aurelia.generate --out data/synthetic     # about 1.4 MB, seeded and reproducible
pytest
```

```python
from aurelia.world import RetailWorld
from aurelia.tools import TOOLS, dispatch

world = RetailWorld.from_dir("data/synthetic")
dispatch(world, "detect_demand_spikes", {})
dispatch(world, "get_inventory_position", {"market": "C", "category": "home"})
```

`TOOLS` is in the Anthropic Messages API format, so it can be passed straight to `tools=` when the
agents are added.

## Run the orchestrator

```bash
python -m aurelia.run --market C --category home                 # offline stand-in, no API key needed
python -m aurelia.run --market C --category home --budget 60000  # over the approval limit, so it stops
python -m aurelia.run --market C --category home --budget 60000 --approve "Your Name"
export ANTHROPIC_API_KEY=...; python -m aurelia.run --live       # Claude, model from AURELIA_MODEL
```

Each run writes a JSON-lines audit trail to `data/audit.jsonl`.

### How the work is split

| Decision | Who makes it |
|---|---|
| Is there a spike, what is driving it, which offer style fits | LLM agents (Sensing, Segmentation) using tools |
| Channel mix, offer type, promo depth, headline | LLM agents (Campaign/Promo, Creative), then checked by code |
| Spend, allocation, replenishment quantity, reallocation, approval tier | Plain code in `decision.py`, from tool results only |
| Approval above EUR 15k, blocks on margin floor or budget cap | Code plus a named human |

The tests include a model that lies about the projected lift and one that proposes an unsafe
campaign and banned claims. In both cases the plan uses the tool numbers or is corrected or stopped.

### Offline stand-in

`OfflineClient` in `llm.py` is a deterministic script that follows the same protocol as the model. It
is not a language model. It lets the whole pipeline run and be tested without an API key. The live
path (`AnthropicClient`) is unit-tested against a fake SDK and has not been run against the real API
from the build environment, so run it once with your key before relying on it.

## The demo scenario

The last five days of the data contain a scripted competitor price cut that lifts Home demand in
Market C. Uncommitted Home stock in Market C is set up to cover roughly 60 to 70 percent of the
projected 14-day lift, so the orchestrator has a real trade-off to resolve. The seed is fixed, so the
scenario is identical on every machine.

## What the tests check

- The generator is reproducible for a given seed and has the expected shape.
- Detection finds injected events (24 of 24 on the default seed) with no false alarms across 40
  market and category series. This is measured on synthetic data with clean injected events, so it
  shows the detector works as designed, not how it would perform on real retail data.
- The demo spike is detected as active on the last data day.
- Every tool returns JSON-serialisable output and rejects bad input with a readable error.

## Layout

```
src/aurelia/config.py     shape of the synthetic world
src/aurelia/generate.py   seeded dataset generator
src/aurelia/detect.py     spike detection
src/aurelia/world.py      read-only tool implementations
src/aurelia/tools.py      Claude tool schemas and dispatcher
src/aurelia/llm.py        LLM client interface, Anthropic client, offline stand-in
src/aurelia/agent.py      tool-use loop with least-privilege tools
src/aurelia/agents.py     prompts and tool lists for the four agents
src/aurelia/decision.py   campaign sizing, guardrails, output validation
src/aurelia/orchestrator.py  analyze and execute, approval gate
src/aurelia/stubs.py      Merchandising and Sourcing stand-ins
src/aurelia/audit.py      JSON-lines audit trail
src/aurelia/run.py        command line entry point
docs/INTERFACES.md        hand-off contracts for Merchandising and Sourcing
docs/BACKLOG.md           weeks 2 and 3
```
