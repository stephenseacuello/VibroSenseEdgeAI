# Contributing to VibroSenseEdgeAI

This is the team's working agreement for code review and the local dev loop. The authoritative project plan is [PROJECT_PLAN.md](PROJECT_PLAN.md); this document is just the *how* of getting changes merged.

## Dev loop (zero to PR in 5 minutes)

```bash
git clone git@github.com:<owner>/VibroSenseEdgeAI.git
cd VibroSenseEdgeAI
make setup        # creates .venv, installs deps, sets up pre-commit
make test         # unit + integration tests
make demo         # exercise the full stack against a real Nano (Pi or dev box)
```

Then:

```bash
git checkout -b se/<scope>-<short-slug>     # e.g. se/ml-quantize-int8
# … hack hack hack …
make lint test                              # before every commit
git commit -m "feat(ml): add INT8 quantization"
git push -u origin HEAD
gh pr create --fill                         # if you have the GitHub CLI
```

## Branches

- **Main is protected.** No direct pushes. All changes land via PR.
- **Branch names.** `<initials>/<scope>-<short-slug>`. Scope is one of `firmware`, `ml`, `gateway`, `app`, `docs`, `infra`.
- **Tags.** Semantic-versioned at each course deliverable: `v0.4-PDR`, `v0.7-CDR`, `v1.0-Final`. Plus weekly minors as useful.

## Commits

Conventional Commits, scope = the top-level folder:

```
feat(ml): add 1D-CNN baseline
fix(gateway): reconnect bleak on dropout
docs: clarify Week 2 hardware procurement
refactor(app): factor create_app into __init__
test(gateway): cover mqtt_to_sqlite happy path
chore(infra): bump pre-commit hooks
```

Body when useful — the **why**, not the **what**. The diff already shows the what.

## Pull requests

- Use the PR template ([`.github/pull_request_template.md`](.github/pull_request_template.md)).
- **At least one reviewer who is not the author.** Block on this even if CI is green.
- Keep PRs small. One concern per PR. If you need to refactor before a fix, do the refactor in its own PR.
- Link the relevant issue and any ATPs the PR satisfies.

### Reviewer checklist

- [ ] CI green
- [ ] Aligns with [PROJECT_PLAN.md](PROJECT_PLAN.md) scope
- [ ] New behavior covered by a test
- [ ] If a payload schema changed, `schema_ver` was bumped and an ADR was added under [`docs/decisions/`](docs/decisions/)
- [ ] No secrets or large binaries committed
- [ ] Public interfaces have docstrings; new modules have a one-line purpose
- [ ] No `TODO` without an owner and a target week (or an OD-N reference)

## Code style

| | |
|---|---|
| Python  | `ruff` + `black` (line length 100). Run `make lint` locally; CI re-checks. |
| C++     | `clang-format`, Google style. Header files end with `.h`; sources with `.cpp`. |
| HTML / JS / CSS | Two-space indent. Keep templates close to plain HTML; behavior in [`app/static/app.js`](app/static/app.js). |
| Tests   | `pytest`. One concept per test. Name them after the behavior being checked, not the function being called. |

Pre-commit runs ruff, black, and basic hygiene hooks. If a hook fails, fix the issue and **re-stage + recommit** — don't `--no-verify`.

## Tests

Always-on:

```bash
make test         # everything pytest can find
pytest -q app/tests                    # only Flask
pytest -q gateway/tests                # only gateway
pytest -q ml/tests/test_features.py    # just one module
```

Gated by `tensorflow` (skips gracefully if not installed):

```bash
pip install -e ".[ml]"
make ml-pipeline   # synth → train → quantize → export → eval
pytest -q ml/tests/test_train_cnn.py
```

## When you change a payload schema

This is a coordinated change across firmware + gateway + app + tests. Order of operations:

1. Add an ADR under [`docs/decisions/`](docs/decisions/) explaining the change.
2. Bump `schema_ver` in [`ml/src/schema.py`](ml/src/schema.py).
3. Update the firmware payload in lockstep ([`firmware/nano33/src/ble_service.cpp`](firmware/nano33/src/ble_service.cpp)).
4. Update [`tests/integration/test_schema.py`](tests/integration/test_schema.py).
5. Note the change in the next deliverable's release notes.

## ADRs (Architecture Decision Records)

Significant decisions get a short markdown file under [`docs/decisions/`](docs/decisions/):

```
0001-ble-payload-schema.md
0002-bearing-fault-method.md
0003-confidence-floor.md
0004-raw-window-protocol.md
```

Template: **Context → Decision → Consequences → Date / Status**. Reference the ADR number in the PR description.

## Issues

Labeled by workstream: `firmware`, `ml`, `gateway`, `app`, `docs`, `infra`. Every issue should have an **owner** and a **target week**. The PM closes stale issues at the weekly status meeting.

## When something is on fire

The pre-final-demo week (Wk 9) is the only place where reverting on red is preferred over rolling forward. Outside that window: write the regression test, ship the fix.

## Hardware checks before flashing a Nano

```bash
make firmware     # arduino-cli compile
PORT=/dev/cu.usbmodemXXXX make flash
```

The `PORT` value depends on your machine — on macOS it's typically `/dev/cu.usbmodem14101`. Confirm with `arduino-cli board list` if unsure.

## Need help?

Surface in the team chat (channel name TBD per [OD-08](PROJECT_PLAN.md#24-open-decisions-register)); escalate to the PM if you're blocked > 24 hours.
