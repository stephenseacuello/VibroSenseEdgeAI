# ADR-0003 — Confidence floor for state-change alarms

**Date:** TBD (lock Wk 6, after first end-to-end run)
**Status:** Open — see [OD-09](../../PROJECT_PLAN.md#24-open-decisions-register)

## Context
The Node-RED state-change detector decides whether a per-window classification
should be promoted to an `alarm` event. Without a confidence floor, marginal
predictions cause the operator HMI tile to flicker between classes and produce
nuisance alarms.

The Flask HMI displays the raw per-window state regardless — the floor only
gates the *alarm* topic and the persisted state-change events Node-RED emits.

## Decision
Default floor: **`confidence >= 0.6`**. Implemented in
`gateway/nodered/flows.json` (`fn.state_change`). Configurable via Node-RED
context if we need to tune per asset.

## Consequences
- Suppresses most flicker at the edges of fault transitions.
- A class with persistent ≤ 0.6 predictions will not raise an alarm — that is
  intentional (it indicates the model is uncertain and a human should look).
- If we observe missed real transitions during Wk 7–8 verification, lower the
  floor or add a second-condition (e.g., N consecutive low-confidence windows
  of the same class).
