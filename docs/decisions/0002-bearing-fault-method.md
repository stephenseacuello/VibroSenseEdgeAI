# ADR-0002 — Bearing-fault simulation method

**Date:** TBD (lock by end of Wk 3, before bulk capture)
**Status:** Open — see [OD-07](../../PROJECT_PLAN.md#24-open-decisions-register)

## Context
The `BEARING_FAULT` class is induced (the asset is a consumer-grade fan, not a
real failed bearing). For train/test consistency we must pick **one** simulation
method and stick with it for the rest of the project. Mixing methods across
sessions changes the within-class distribution and risks splitting the class
into two clusters the model has to learn separately.

Candidates from PROJECT_PLAN.md §9.2.3:

- **A. Rubber-band radial drag.** Loop a rubber band over the motor housing to
  add light radial load on the shaft. Pros: fully reversible, no disassembly.
  Cons: tension is hard to make repeatable across sessions.
- **B. Abrasive on bearing race.** Brief disassembly; fine sandpaper or pumice
  paste applied to an accessible race. Pros: realistic damage signature.
  Cons: irreversible; we may go through several test assets.
- **C. Axial shim misalignment.** Slight shim under one motor mount foot. Pros:
  reversible; parameter (shim thickness) is precisely measurable. Cons: more an
  alignment fault than a bearing fault per se — may collide with `LOOSENESS`.

## Decision
TBD. Mechanical lead + ML lead pick one and freeze parameters here.

## Consequences
TBD — fill in when locked.
