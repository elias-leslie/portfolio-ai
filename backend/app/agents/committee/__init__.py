"""Investment Committee — multi-agent /portfolio/committee decision pipeline.

See plans/sunny-puzzling-sprout.md for the full design. This package owns:

- ``graph`` — the orchestrator (``run_committee``)
- ``stages`` — per-role stage helpers calling Agent Hub
- ``ips`` — deterministic IPS checks wired to existing portfolio utilities
- ``store`` — append-only DB persistence (events, evidence, inputs, decisions)
- ``stream`` — per-run asyncio.Queue registry + pause/resume/abort control
- ``feedback`` — anti-sycophancy consensus-shift rule
- ``schemas`` — typed payloads for stages + events
"""

GRAPH_VERSION = "committee.v0.3.1"
