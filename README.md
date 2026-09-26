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
| Agents, orchestrator, guardrails, audit log | week 2, see `docs/BACKLOG.md` |
| Backtest and live dashboard | week 3 |

## Quickstart

```bash
pip install -e ".[dev]"
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
docs/INTERFACES.md        hand-off contracts for Merchandising and Sourcing
docs/BACKLOG.md           weeks 2 and 3
```
