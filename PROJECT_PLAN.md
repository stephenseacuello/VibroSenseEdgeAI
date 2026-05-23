# VibroSenseEdgeAI — Project Plan

**Edge-AI Predictive Maintenance for a Small Rotating Asset**
*ISE 575: Industry 4.0 Special Projects — Summer 2026, University of Rhode Island*

> *"From vibration to decision, on-device."*

| | |
|---|---|
| **Team** | VibroSense Edge AI |
| **Members** | Andrew Muszynski, Stephen Eacuello (PM), Michael Reinhart |
| **Sponsor / Instructor** | Dr. Lance Decker |
| **Duration** | 10 weeks (Summer 2026) |
| **Repository** | `github.com/<owner>/VibroSenseEdgeAI` (to be created) |
| **Charter Source** | `Week01_ProjectCharter_v6.docx` (authoritative) |
| **Plan Version** | v0.2 — 2026-05-22 |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Goals & Success Criteria](#2-goals--success-criteria)
3. [System Architecture (ISA-95 Layered)](#3-system-architecture-isa-95-layered)
4. [Performance Budgets](#4-performance-budgets)
5. [Technology Stack](#5-technology-stack)
6. [Repository Structure & Conventions](#6-repository-structure--conventions)
7. [Workstreams, Ownership & Definition of Done](#7-workstreams-ownership--definition-of-done)
8. [10-Week Milestone Plan](#8-10-week-milestone-plan)
9. [Data Plan](#9-data-plan)
10. [ML Pipeline Plan](#10-ml-pipeline-plan)
11. [Firmware Plan (Arduino Nano 33 BLE Sense)](#11-firmware-plan-arduino-nano-33-ble-sense)
12. [Gateway & Supervisory Plan (Raspberry Pi)](#12-gateway--supervisory-plan-raspberry-pi)
13. [Flask Application Plan](#13-flask-application-plan)
14. [Interface Contracts](#14-interface-contracts)
15. [Test & Verification — Acceptance Test Procedures](#15-test--verification--acceptance-test-procedures)
16. [Final Demo Script (Week 10)](#16-final-demo-script-week-10)
17. [Risk Register](#17-risk-register)
18. [Budget](#18-budget)
19. [Communication Plan & Decision Log](#19-communication-plan--decision-log)
20. [Deliverables Checklist](#20-deliverables-checklist)
21. [GitHub Workflow](#21-github-workflow)
22. [Onboarding — Quick Start](#22-onboarding--quick-start)
23. [CLO Traceability Matrix](#23-clo-traceability-matrix)
24. [Open Decisions Register](#24-open-decisions-register)
25. [Glossary & References](#25-glossary--references)

---

## 1. Executive Summary

Vibration-based predictive maintenance has historically required expensive industrial sensors, dedicated PLC channels, and cloud analytics — a cost stack that excludes lower-criticality rotating assets that nevertheless accumulate substantial plant downtime. TinyML changes the economics: a quantized neural network running on a sub-$30 microcontroller can classify vibration patterns in real time, on-device, without continuous connectivity.

VibroSenseEdgeAI demonstrates the approach end-to-end on a real consumer-grade rotating asset. We instrument it with an Arduino Nano 33 BLE Sense, collect labeled vibration data across one healthy and three induced fault states, train and INT8-quantize a 1D-CNN classifier in Python, deploy to the Nano via TensorFlow Lite Micro, transport inference results over BLE to a Raspberry Pi 4 gateway, and integrate the live output into a Flask operator HMI backed by Node-RED, MQTT, and SQLite.

The system spans **ISA-95 Levels 0–3** (Physical → Sensing/Control → Supervisory → MES). Level 4 (Business/ERP) is intentionally out of scope. The AI/ML inference layer plus the Flask operations UI together fulfill the MES role.

---

## 2. Goals & Success Criteria

### 2.1 SMART Objectives

- **Specific.** Classify four states — `HEALTHY`, `IMBALANCE`, `LOOSENESS`, `BEARING_FAULT` — on-device, and publish predictions over BLE to a Pi gateway and Flask HMI.
- **Measurable.** ≥ 90% accuracy on held-out test set; < 250 ms inference per window on-device; quantized model fits Nano flash budget; live demo correctly identifies each fault ≥ 3 of 4 trials.
- **Achievable.** Every component has precedent in ISE 571 (PLC/SCADA), ISE 572 (ML), ISE 573 (MES).
- **Relevant.** Hits all five ISE 575 Course Learning Objectives (CLOs 1–5).
- **Time-bound.** All deliverables due 11:59 p.m. Sunday of Week 10.

### 2.2 Acceptance Criteria (binary, evaluated at Week 10)

| ID | Criterion | Source | Verified by |
|---|---|---|---|
| AC-1 | Held-out test-set accuracy ≥ 90% | Charter §3 | ATP-05 |
| AC-2 | On-device inference latency p95 < 250 ms | Charter §3 | ATP-01 |
| AC-3 | Quantized model fits within Nano flash budget with ≥ 30% headroom | Charter §10.1 | ATP-02 |
| AC-4 | Live demo: each fault correctly identified ≥ 3 of 4 trials | Charter §3 | ATP-09 |
| AC-5 | Flask operator tile updates within 1 s of state change | Charter §4.3 UC-1 | ATP-07 |
| AC-6 | Every classification persisted to SQLite (no drops over 30-min soak) | Charter §4.1 | ATP-08 |
| AC-7 | `/api/v1/oee` returns sensible availability across a known fault sequence | Charter §4.3 UC-3 | ATP-10 |
| AC-8 | Source code shipped as a tagged GitHub release with README, build, run procedure | Charter §11.1 | Manual review |

### 2.3 Exit / Pivot Criteria

| Trigger | Pivot |
|---|---|
| Nano / shield lost or damaged and unreplaceable by Week 7 | Software-only TinyML demo on a public vibration dataset (CWRU bearing dataset as a candidate) |
| End of Week 5: model cannot fit Nano memory budget despite §17 mitigations | Fall back to a **two-class** model (Healthy vs Fault) — protects the demo |
| > 50% of team unavailable for an extended period | PM escalates to instructor per Team Charter |

---

## 3. System Architecture (ISA-95 Layered)

```
┌────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — Operations Mgmt & UI  (ISA-95 Level 3, MES)             │
│  Flask app: operator HMI tile · engineering trend view · REST      │
│  /api/v1/{state,history,oee} · WebSocket live push · Chart.js      │
└──────────────────────────────▲─────────────────────────────────────┘
                               │  HTTP / WS (localhost on Pi)
┌──────────────────────────────┴─────────────────────────────────────┐
│  LAYER 3 — Gateway Services      (ISA-95 Level 2, Supervisory)     │
│  Raspberry Pi 4 · Python BLE-central (bleak) → Mosquitto MQTT      │
│  → Node-RED orchestration (state machine, alarms, OEE) → SQLite    │
└──────────────────────────────▲─────────────────────────────────────┘
                               │  BLE GATT notify (JSON, schema v1)
┌──────────────────────────────┴─────────────────────────────────────┐
│  LAYER 2 — Wireless Transport (Infrastructure)                     │
│  BLE 5.0 GATT, versioned JSON payload                              │
└──────────────────────────────▲─────────────────────────────────────┘
                               │
┌──────────────────────────────┴─────────────────────────────────────┐
│  LAYER 1 — Edge Inference        (ISA-95 Level 1, Sensing/Control) │
│  Arduino Nano 33 BLE Sense + Tiny ML Shield · LSM9DS1 IMU          │
│  Sample → window → TFLite Micro inference → BLE GATT characteristic│
└──────────────────────────────▲─────────────────────────────────────┘
                               │  rigid mechanical coupling
┌──────────────────────────────┴─────────────────────────────────────┐
│  LAYER 0 — Physical Asset        (ISA-95 Level 0)                  │
│  Small consumer-grade rotating asset (TBD Week 2) on fixed mount   │
└────────────────────────────────────────────────────────────────────┘
```

**ISA-95 mapping:** covers Levels 0–3 (4 of 5). Level 4 (Business/ERP) is out of scope by design.

---

## 4. Performance Budgets

### 4.1 End-to-End Latency Budget (sample → UI render)

Targeting **< 1.0 s** sample-to-operator-tile-update under nominal conditions.

| Stage | Where | Budget | Notes / how to measure |
|---|---|---|---|
| Window collection (256 samples @ ~952 Hz) | Nano | ~270 ms | Overlaps with previous inference; not on critical path after steady-state |
| Feature pre-processing (if used) | Nano | < 10 ms | Wall-clock via `micros()` |
| **TFLite Micro inference** | **Nano** | **< 250 ms (p95)** | **AC-2 — hard target** |
| JSON serialize + BLE notify TX | Nano | < 50 ms | Dominated by BLE connection interval |
| BLE notify RX (bleak) | Pi | < 50 ms | Pi connection interval setting |
| MQTT publish + Node-RED route | Pi | < 30 ms | Local broker, QoS 0 for state |
| SQLite insert | Pi | < 20 ms | Append-only, single-writer |
| WebSocket push | Pi → browser | < 50 ms | LAN |
| Browser render | Client | < 100 ms | Chart.js update is the heaviest UI op |
| **Total (p95)** | | **< ~830 ms** | Comfortably under 1 s target |

### 4.2 Nano 33 BLE Sense Memory Budget (nRF52840)

Total resources: 1 MB flash, 256 KB SRAM. Soft Device (BLE stack) consumes part of both before the user app sees them.

| Allocation | Flash | SRAM | Note |
|---|---|---|---|
| Soft Device + bootloader | ~160 KB | ~24 KB | Vendor-fixed |
| Arduino core + ArduinoBLE + Arduino_LSM9DS1 | ~120 KB | ~20 KB | Estimate; re-measure with `arduino-cli compile --show-properties` |
| **TFLite Micro runtime** | **~80 KB** | — | Op resolver pruned to the ops we use |
| **TFLite Micro tensor arena** | — | **24–40 KB** | Tune per model; characterize in Wk 5 |
| **Model (`model.h`, INT8)** | **< 30 KB (target)** | — | Pre-quant target < 100 KB (charter §10.1) |
| App code (sample loop, feature extract, JSON, BLE service) | ~30 KB | ~8 KB | |
| Ring buffer + feature window | — | ~6 KB | `256 × 3 × float32 ≈ 3 KB` plus working copies |
| **Sub-total** | **~420 KB** | **~92 KB** | |
| **Headroom (target ≥ 30%)** | ~580 KB | ~164 KB | Confirmed at PDR gate |

> Numbers above are working estimates; actual values populated by the Week 5 build report (commit on `v0.5` tag).

### 4.3 Power Budget (informational, not a gate)

Characterize current draw in Week 3 (charter §10.1). Working assumption is sub-25 mA RMS during inference; CR2032 has ~225 mAh, so a continuous run is bench-only — operate from USB during data capture and demo. AA pack is the fallback for portable demo.

---

## 5. Technology Stack

| Layer | Tools |
|---|---|
| **Edge (L1)** | Arduino IDE / `arduino-cli`, C++17, TensorFlow Lite Micro, ArduinoBLE, Arduino_LSM9DS1 |
| **ML pipeline** | Python 3.11, NumPy, pandas, scikit-learn, TensorFlow/Keras, TFLite converter (INT8), Jupyter |
| **BLE central** | Python 3.11, `bleak` (cross-platform BLE) |
| **Messaging** | Mosquitto MQTT broker |
| **Orchestration** | Node-RED |
| **Persistence** | SQLite (time-series append-only) |
| **App layer** | Python Flask, Flask-SocketIO, Jinja2, Chart.js |
| **Dev/CI** | Git, GitHub, GitHub Actions, pytest, ruff, black, pre-commit |

---

## 6. Repository Structure & Conventions

### 6.1 Layout

```
VibroSenseEdgeAI/
├── README.md                       # Build, schema, run procedure
├── PROJECT_PLAN.md                 # ← this file
├── CONTRIBUTING.md                 # team dev loop, code-review rules
├── LICENSE                         # MIT (proposed)
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml                  # ruff/black/pytest config
├── Makefile                        # canonical task entrypoints (see §22)
├── .github/
│   ├── workflows/                  # CI: lint, pytest, model artifact build
│   └── pull_request_template.md
├── docs/
│   ├── charter/                    # signed charter PDFs
│   ├── design/                     # PDR & CDR slides, block diagrams
│   ├── test-plan/                  # Test Plan v1 → final
│   ├── decisions/                  # ADRs (architecture decision records)
│   ├── lessons-learned.md
│   └── schematics/                 # wiring diagrams, mounting fixture
├── firmware/
│   └── nano33/
│       ├── nano33.ino              # main sketch
│       ├── src/                    # feature extraction, BLE, inference
│       ├── model/                  # generated model.h (INT8 TFLite)
│       └── platformio.ini          # or arduino-cli config
├── ml/
│   ├── notebooks/                  # exploratory training notebooks
│   ├── data/
│   │   ├── raw/                    # captured windows (.parquet, LFS)
│   │   ├── processed/
│   │   └── README.md               # dataset card
│   ├── src/
│   │   ├── capture.py              # BLE-streamed raw-window capture (ADR-0004)
│   │   ├── raw_window.py           # binary protocol encode/decode (ADR-0004)
│   │   ├── schema.py               # pydantic StateV1
│   │   ├── features.py             # FFT, RMS, kurtosis, etc.
│   │   ├── baseline_rf.py          # sklearn RandomForest baseline
│   │   ├── train_cnn.py            # 1D-CNN training
│   │   ├── quantize.py             # INT8 conversion to TFLite
│   │   ├── export.py               # TFLite → C array (model.h)
│   │   └── eval.py                 # ATP-05 evaluator (accuracy / per-class recall / CM)
│   ├── experiments/                # one markdown file per run
│   └── tests/                      # features, raw_window, baseline_rf, train_cnn, eval, quantize_export
├── gateway/
│   ├── ble_central.py              # bleak subscriber → MQTT publisher (validates StateV1)
│   ├── mqtt_to_sqlite.py           # MQTT subscriber → SQLite persister
│   ├── nodered/flows.json          # exported Node-RED flows
│   ├── mosquitto/mosquitto.conf
│   ├── db/schema.sql               # SQLite schema (events table)
│   ├── systemd/                    # service units for headless boot
│   └── tests/                      # test_{ble_central,mqtt_to_sqlite}.py
├── app/
│   ├── __init__.py                 # create_app() factory (composition root)
│   ├── app.py                      # `python -m app.app` entrypoint
│   ├── config.py                   # env-driven Config class
│   ├── extensions.py               # SocketIO singleton
│   ├── db.py                       # SQLite helper + teardown registration
│   ├── errors.py                   # 404/405/500 (JSON for /api/*, HTML else)
│   ├── sockets.py                  # SocketIO connect/disconnect handlers
│   ├── mqtt_bridge.py              # MQTT subscriber → SocketIO emit (validates)
│   ├── routes/
│   │   ├── hmi.py                  # GET /
│   │   ├── trend.py                # GET /trend
│   │   ├── about.py                # GET /about (build info + DB stats)
│   │   ├── health.py               # GET /healthz, /readyz
│   │   └── api.py                  # /api/v1/{state,history,oee,assets}
│   ├── templates/
│   │   ├── base.html               # nav + connection indicator
│   │   ├── hmi.html, trend.html, about.html
│   │   └── errors/{404,500}.html
│   ├── static/                     # style.css, app.js (shared socket), favicon.svg
│   ├── tests/                      # conftest + test_{api,health,errors,bridge}.py
│   └── README.md                   # app-level docs
├── scripts/
│   ├── bootstrap_pi.sh             # one-shot Pi provisioning
│   ├── run_demo.sh                 # end-to-end local demo
│   └── synth_dataset.py            # synthetic 4-class dataset generator (CI / test fixture only)
└── tests/
    └── integration/                # cross-layer integration tests (schema, end-to-end)
```

### 6.2 Conventions

- **Commit messages.** Conventional Commits: `feat(ml): add 1D-CNN baseline`, `fix(gateway): reconnect bleak on dropout`, `docs: update README run procedure`. Scope is the top-level folder.
- **Branch names.** `<initials>/<scope>-<short-slug>`, e.g. `se/ml-quantize-int8`.
- **PR titles** mirror commit messages; PR body uses the template (link to issue + test evidence).
- **Code style.** Python via `ruff` + `black` (line length 100). C++ via `clang-format` (Google style). Enforced by `pre-commit`.
- **No commits to `main`.** PRs only, one reviewer who is not the author.
- **Tags.** Semantic-versioned, one per deliverable: `v0.4-PDR`, `v0.7-CDR`, `v1.0-Final`, plus weekly minors as useful (`v0.3`, `v0.5`, …).
- **Data files.** Anything > 5 MB uses Git LFS or an out-of-band store referenced by SHA in `ml/data/README.md`.

### 6.3 Architecture Decision Records (ADRs)

Each significant decision gets a numbered markdown file under `docs/decisions/`:

```
docs/decisions/0001-ble-payload-schema.md
docs/decisions/0002-cnn-vs-rf-on-device.md
```

Template: **Context → Options considered → Decision → Consequences → Date / Author**. Mention the ADR number in the PR that implements it.

---

## 7. Workstreams, Ownership & Definition of Done

Two-deep coverage on every workstream (charter §10.1). Primary drives; backup reviews PRs and can step in within 24 h on absence.

### 7.1 Owners

| Workstream | Primary | Backup |
|---|---|---|
| Firmware (Nano, BLE, TFLite Micro) | *TBD Wk 2* | *TBD* |
| ML pipeline (capture → train → quantize → export) | *TBD* | *TBD* |
| Gateway (bleak, MQTT, Node-RED, SQLite) | *TBD* | *TBD* |
| Flask app (HMI, trend, REST, WebSocket) | *TBD* | *TBD* |
| Mechanical (mounting fixture, fault injection) | *TBD* | *TBD* |
| PM / documentation / deliverables | Stephen Eacuello | *TBD* |

> Lock owners in Week 2. Document in [OD-04](#24-open-decisions-register).

### 7.2 Definition of Done (per workstream)

**Firmware** — sketch builds clean (`arduino-cli compile` zero warnings); flashes to a Nano via documented command in README; BLE service advertises with documented UUIDs; `state` characteristic emits valid schema-v1 JSON at ≥ 1 Hz; latency (ATP-01) and memory (ATP-02) gates pass.

**ML pipeline** — `make train` runs end-to-end from a checked-in dataset SHA to a `model.h` artifact; ATP-05 (test-set accuracy) passes; experiment log entry committed with metrics + confusion matrix.

**Gateway** — `bleak` central reconnects automatically across BLE dropouts (ATP-06); every `state` message reaches SQLite (ATP-08); Node-RED flows exported to `gateway/nodered/flows.json`; `systemd` units bring the stack up on boot.

**Flask app** — operator tile updates within 1 s of state change (ATP-07); trend view renders last 5 min from SQLite; `/api/v1/state`, `/api/v1/history`, `/api/v1/oee` all return documented JSON; smoke-tested in pytest.

**Mechanical** — fixture documented in `docs/schematics/`; each fault repeatable per the SOPs in §9.2 (ATP-09); imbalance mass set calibrated.

**PM / docs** — every deliverable submitted by deadline; final report formatted per course standard (Times New Roman 12 pt, double-spaced, 1-inch margins, lower-right page numbers, APA citations); README contains build, schema, and run procedure.

---

## 8. 10-Week Milestone Plan

Each row has an **entry gate** (what must be true to start the week) and an **exit gate** (what must be true to finish). Exit gates are evaluated at the weekly status meeting.

| Wk | Theme | Entry gate | Key tasks | Deliverable | Exit gate |
|---|---|---|---|---|---|
| **1** | Kickoff | — | Team Charter; pitch video; draft charter; hardware inventory | Team Charter · Pitch Video · Draft Charter | Charter approved by sponsor |
| **2** | Lock scope | Charter approved | Finalize charter; start Test Plan; select test asset; prove BLE Nano↔Pi; create GitHub repo; fill owner table | Final Charter · Draft Test Plan · `v0.2` tag | BLE round-trip demo; repo live; owners locked |
| **3** | Capture rig | BLE proven | Build mounting fixture; Python capture tool; first dataset (Healthy only) | Final Test Plan · Baseline Dataset v1 · `v0.3` | Capture tool runs on three dev machines; ≥ 30 min Healthy captured |
| **4** | Modeling | Healthy dataset in hand | Capture full 4-class labeled dataset; sklearn RF baseline; 1D-CNN trained in Python | **PDR Video** · `v0.4-PDR` | RF ≥ 80% test-set accuracy on stratified split |
| **5** | Quantize & deploy | CNN trained | INT8 conversion; on-device inference; `state` published over BLE | Discussion post · firmware build · `v0.5` | ATP-01 passes (latency p95 < 250 ms); ATP-02 passes (memory) |
| **6** | Supervisory stack | Inference on-device | Pi BLE-central → Mosquitto → Node-RED → SQLite end-to-end | Discussion post · integration test results · `v0.6` | ATP-06 + ATP-08 pass; one classification round-trips Nano→DB |
| **7** | Operations UI | Gateway stack up | Flask HMI tile + trend view + REST + WebSocket; end-to-end demo | **CDR Video** · `v0.7-CDR` | Full stack runs unattended ≥ 30 min; ATP-07 passes |
| **8** | Verify & harden | CDR shipped | Execute full Test Plan; open & burn down defect log | Test results package · `v0.8` | All ATPs pass; all P0/P1 defects closed |
| **9** | Polish | All ATPs green | Draft final report; rehearse demo; assemble documentation set | Draft Final Report · `v0.9` | Dry-run demo recorded; report ready for review |
| **10** | Ship | Dry-run clean | Final demo recording; lessons learned; tagged source release | **Final Demo Video · Final Report · Source Code (`v1.0-Final`)** | All charter deliverables submitted |

---

## 9. Data Plan

### 9.1 Asset & Classes

- **Asset.** Consumer-grade rotating asset, ≤ $100, locked in Week 2. Working assumption: basic desk fan or smart fan with oscillation and speed controls. Selection criteria: stable mounting surface; multiple speeds; accessible blade/hub for imbalance injection; quiet enough to run indoors for hours.
- **Classes (4).**

| Label | Description |
|---|---|
| `HEALTHY` | Baseline, factory condition, no induced fault |
| `IMBALANCE` | Calibrated mass added to one blade / hub asymmetry |
| `LOOSENESS` | Mounting screw/bracket loosened by a documented amount |
| `BEARING_FAULT` | Simulated bearing degradation (see §9.2.3) |

### 9.2 Fault Injection SOPs (repeatable so train ≈ test)

Each fault is injected the same way every time. The goal is to make the demo reproducible and to ensure the training distribution matches what we'll demonstrate live. Every capture session records the *exact* fault parameters in the session metadata.

#### 9.2.1 `IMBALANCE`
1. Confirm asset is unplugged and blades stationary.
2. Select one calibrated mass from the labeled mass set (e.g., 0.5 g, 1.0 g, 2.0 g washers).
3. Attach to a documented position on a specific blade (mark blade `B1` with paint or label).
4. Record `mass_g` and `position` (e.g., `B1-tip`, `B1-mid`) in session metadata.
5. Capture ≥ 5 min per speed setting; rotate which mass / position across sessions to vary the within-class distribution.

#### 9.2.2 `LOOSENESS`
1. Identify the mounting bolt sequence (`M1, M2, M3, M4`).
2. Loosen one bolt by a documented number of turns (e.g., `1.5 turns`).
3. Record `bolt_id` and `turns_loose` in metadata.
4. Capture; restore to torqued state and verify with `HEALTHY` recapture before the next session.

#### 9.2.3 `BEARING_FAULT`
1. Choose one of the approved simulators (pick one and stick with it; switching mid-project changes the distribution):
   - **A.** Light radial drag on the shaft via a rubber band looped over the motor housing.
   - **B.** Light abrasive (fine sandpaper or kitchen-grade pumice paste) applied to an accessible bearing race during a brief disassembly.
   - **C.** Slight axial misalignment via a shim under one motor mount.
2. Document method letter and parameters (band tension, paste grit, shim thickness) in session metadata.
3. Capture.

> **Train/test split discipline:** never train and test on the *same* session of a given fault parameter set. Stratify splits by `session_id` (see §9.4) to prevent temporal leakage.

### 9.3 Capture Protocol

- **Sample rate.** LSM9DS1 default accel ODR ~952 Hz — confirm in Week 3 and freeze.
- **Window size.** Target 256 or 512 samples (~270–540 ms). Tune in Week 4; lock at PDR.
- **Per class.** ≥ 30 minutes of stationary capture, across multiple sessions, varied fan speeds where applicable.
- **Session template.** Each capture session records:
  ```yaml
  session_id: 2026-07-12_HEALTHY_speed-2_amuszynski
  capture_date_utc: 2026-07-12T15:04:00Z
  operator: amuszynski
  asset_id: fan-01
  class_label: HEALTHY
  speed_setting: 2
  ambient_notes: "room temp ~22C, fan oscillation OFF, mounted on workbench A"
  fault_params: {}     # populated for non-HEALTHY classes
  sample_rate_hz: 952
  window_size: 256
  firmware_sha: "<git short SHA>"
  ```
- **Splits.** 70/15/15 train/val/test, **stratified by `session_id`**. No session appears in more than one split.

### 9.4 Data Quality Checks (run inline by `capture.py`)

The capture tool refuses to save a session that fails any of these checks. This catches sensor mis-mounts and clipping early instead of after a training run.

| Check | Threshold | Why |
|---|---|---|
| Mean |a| within 0.9–1.1 g on the gravity axis | Sensor orientation correct |
| Per-window NaN/Inf count | 0 | Sensor or BLE corruption |
| Per-axis clipping rate | < 0.1% of samples saturated | Range too low |
| Sample rate drift | < 5% from nominal | BLE backpressure |
| Session duration | ≥ 3 min | Avoid dribble sessions |
| Per-class total | track running total against 30-min target | Visibility |

### 9.5 Storage & Versioning

- Raw windows in `ml/data/raw/*.parquet`. **Do not commit large data directly** — use Git LFS or an out-of-band store with a SHA-256 manifest in `ml/data/README.md` (the dataset card).
- Every model training run cites the dataset manifest SHA in its experiment log.

---

## 10. ML Pipeline Plan

### 10.1 Features (for RF baseline + auxiliary inputs)

Time-domain (per axis): RMS, peak, peak-to-peak, kurtosis, crest factor, skewness.
Frequency-domain (per axis): FFT magnitude bins (low-resolution, e.g., 16 bins); dominant frequency; energy in 1×–4× running-speed bands.

### 10.2 Models

| Model | Purpose | Library | Target footprint |
|---|---|---|---|
| **scikit-learn RandomForest** | Baseline; sanity-check feature separability | sklearn | host-only, no size cap |
| **1D-CNN (Keras → TFLite Micro)** | Production model on Nano | TensorFlow 2.x | < 100 KB pre-quant, < 30 KB INT8 |

### 10.3 Concrete 1D-CNN Architecture (working spec)

Locked at the PDR gate (Week 4) — adjust as needed against memory and accuracy results.

```python
# input: (window_size=256, channels=3)  --> ax, ay, az
model = keras.Sequential([
    layers.Input(shape=(256, 3)),
    layers.Conv1D(8,  kernel_size=5, activation="relu", padding="same"),
    layers.MaxPool1D(pool_size=2),                  # 128 × 8
    layers.Conv1D(16, kernel_size=5, activation="relu", padding="same"),
    layers.MaxPool1D(pool_size=2),                  # 64 × 16
    layers.Conv1D(32, kernel_size=3, activation="relu", padding="same"),
    layers.GlobalAveragePooling1D(),                # 32
    layers.Dense(16, activation="relu"),
    layers.Dropout(0.3),
    layers.Dense(4,  activation="softmax"),
])
```

- **Parameter count (rough):** ~3–5K trainable params.
- **Pre-quant size:** ~20–30 KB.
- **Post-INT8 size:** target < 15 KB.
- **Loss:** sparse categorical cross-entropy.
- **Optimizer:** Adam, lr=1e-3, ReduceLROnPlateau on val_loss.
- **Class balancing:** weighted loss based on class counts; verify confusion matrix is not dominated by majority class.
- **Augmentation (training only):** mild Gaussian noise (σ ≈ 0.01 g); small random time shifts within window.

### 10.4 Quantization & Export

- Post-training **INT8 quantization** with a representative dataset slice (≥ 100 random windows from the train split).
- Export TFLite → C array (`model.h`) via `xxd -i` or the TFLite Micro example pipeline.
- Verify in two places: (a) host-side TFLite Python runtime accuracy ≈ Keras accuracy; (b) on-device latency < 250 ms.

### 10.5 Experiment Tracking

Plain-text `ml/experiments/YYYY-MM-DD_<slug>.md` per run:

```markdown
---
date_utc: 2026-07-15T18:22:00Z
operator: muszynski
dataset_sha: abc123…
code_sha: def456…
---

## Hyperparameters
window_size: 256
batch_size: 64
epochs: 60
lr: 1e-3

## Results
train_acc: 0.97   val_acc: 0.93   test_acc: 0.91
model_size_pre_quant_kb: 24
model_size_int8_kb: 12
on_device_latency_ms_p95: 210

## Confusion matrix
                 pred_H  pred_I  pred_L  pred_B
actual_HEALTHY     ...
…

## Notes
Bearing/looseness occasionally confused at fan speed 1.
```

Reproducibility > tooling — keeps us off MLflow until/unless we need it.

---

## 11. Firmware Plan (Arduino Nano 33 BLE Sense)

### 11.1 Responsibilities

1. Configure LSM9DS1 IMU at fixed ODR; verify with a startup self-test.
2. Maintain a ring buffer; emit fixed-size, non-overlapping (or 50%-overlap) feature windows.
3. Run TFLite Micro inference per window.
4. Publish `{state, confidence, ts_ms, seq}` as a BLE GATT characteristic (notify).
5. Mode characteristic: `INFER` (default) vs `CAPTURE` (raw windows out for data collection).
6. Watchdog: if BLE stalls > 30 s, reset radio.

### 11.2 BLE GATT Layout (draft — finalize Week 2)

Generate 128-bit UUIDs via `uuidgen` and freeze them in [ADR-0001](docs/decisions/0001-ble-payload-schema.md).

| Service | Char | Properties | Format |
|---|---|---|---|
| VibroSense PDM | `state` | notify | JSON, schema v1 (see §14.1) |
| | `raw_window` | notify | chunked binary frames per [ADR-0004](docs/decisions/0004-raw-window-protocol.md) — int16 triples, scale = 1000 |
| | `mode` | read/write | uint8: `0=INFER`, `1=CAPTURE` |
| | `version` | read | UTF-8 string: `firmware_sha + schema_ver` |

The `raw_window` chunking is implemented in [`firmware/nano33/src/ble_service.cpp`](firmware/nano33/src/ble_service.cpp) (`publishRawWindow`) and reassembled on the Python side by [`ml/src/raw_window.WindowAssembler`](ml/src/raw_window.py) — see ADR-0004 for the byte-level layout.

### 11.3 Memory & Latency

See §4.1 (latency) and §4.2 (memory). Build report goes into the `v0.5` tag notes.

### 11.4 Power

Charter §10.1: characterize current draw in Week 3; sleep between windows; AA pack as battery fallback if CR2032 sag observed.

---

## 12. Gateway & Supervisory Plan (Raspberry Pi)

### 12.1 Service Topology (all on one Pi 4, systemd-managed)

```
[BLE central (bleak, Python)]
        │ JSON over MQTT (QoS 0 for state, QoS 1 for alarms)
        ▼
[Mosquitto MQTT broker]
        │
        ▼
[Node-RED flows]   ── state machine ── alarm routing ── OEE calculator
        │
        ▼
[SQLite]   ◄── append-only events table
        ▲
        │ read
[Flask app, REST + WebSocket]
```

### 12.2 MQTT Topic Structure

| Topic | Purpose | QoS | Retained |
|---|---|---|---|
| `pdm/{asset_id}/state` | Per-window classification | 0 | No |
| `pdm/{asset_id}/features` | Optional feature vector for debugging | 0 | No |
| `pdm/{asset_id}/raw_window` | Optional raw IMU window | 0 | No |
| `pdm/{asset_id}/alarm` | Node-RED-issued alarms | 1 | Yes |
| `pdm/{asset_id}/oee` | Rolling availability KPI | 0 | Yes |

### 12.3 SQLite Schema (initial)

```sql
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    TEXT    NOT NULL,
    ts_utc      TEXT    NOT NULL,            -- ISO 8601
    state       TEXT    NOT NULL,            -- HEALTHY|IMBALANCE|LOOSENESS|BEARING_FAULT
    confidence  REAL    NOT NULL,            -- 0..1
    seq         INTEGER NOT NULL,            -- monotonic per session, from device
    schema_ver  INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX ix_events_asset_ts ON events (asset_id, ts_utc);
```

### 12.4 Node-RED Flow Logic (sketch)

- **State-change detector.** Compare current message against last persisted state; only emit transitions as `alarm` topic events.
- **Confidence floor.** Drop messages with `confidence < 0.6` to suppress flicker (tunable; record default in [ADR-0003](docs/decisions/0003-confidence-floor.md)).
- **OEE calculator.** Rolling 1-min window: `availability = time_HEALTHY / total_time`. Publish to `pdm/{asset_id}/oee` retained at 0.1 Hz.

---

## 13. Flask Application Plan

### 13.1 Pages

| Route | Purpose |
|---|---|
| `/` | **Operator HMI** — single-tile current state; color-coded by class; banner on non-healthy; last-update timestamp |
| `/trend` | **Engineering trend view** — Chart.js over SQLite; last 5 min default; selectable range |
| `/about` | Build info: firmware SHA, model SHA, app version (debug aid) |

### 13.2 REST API

| Endpoint | Returns |
|---|---|
| `GET /api/v1/state?asset_id=<id>` | Current state, confidence, ts, seq |
| `GET /api/v1/history?from=<ISO>&to=<ISO>&asset_id=<id>` | Time-series of classifications |
| `GET /api/v1/oee?window=<seconds>&asset_id=<id>` | Availability-style KPI: % time `HEALTHY` over a window |
| `GET /api/v1/assets` | Known asset_ids with counts and last_ts |
| `GET /healthz`, `GET /readyz` | Liveness + readiness probes (systemd / monitoring) |

All `/api/*` failures return the error envelope from §14.4. Param validation: `BAD_RANGE` for ISO-8601 violations, `BAD_PARAM` for non-positive `window`, `NO_DATA` for missing asset, `NOT_FOUND` for unknown routes, `METHOD_NOT_ALLOWED` for non-GET.

### 13.3 WebSocket

`/socket.io/` — pushes each new state event to subscribed clients. Same shape as the MQTT `state` message (§14.2). On client connect the server immediately emits the latest persisted state from SQLite so a fresh page never shows "—" when there's data on disk. All inbound MQTT payloads are re-validated against `StateV1` before fan-out (defense in depth on top of the gateway-side check; ATP-04).

### 13.4 HMI Wireframe (text)

```
┌─────────────────────────────────────────────────────────────────────┐
│  VibroSense Edge AI   ●  fan-01    [ Operator | Trend | About ]    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│     ┌───────────────────────────────────────────────────────┐       │
│     │                                                       │       │
│     │                    HEALTHY                            │       │
│     │                                                       │       │
│     │              confidence: 0.94                         │       │
│     │              updated: 14:32:10 UTC                    │       │
│     │                                                       │       │
│     └───────────────────────────────────────────────────────┘       │
│                                                                     │
│  Tile background: green=HEALTHY, amber=IMBALANCE/LOOSENESS,         │
│                    red=BEARING_FAULT.                               │
│  Banner shown when non-HEALTHY: "FAULT DETECTED — see Trend"        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 14. Interface Contracts

All cross-layer payloads versioned. Bumping `schema_ver` is a deliberate, documented action (PR + ADR).

### 14.1 BLE → Gateway (`state` characteristic, schema v1)

```json
{
  "schema_ver": 1,
  "ts_ms": 12345678,
  "seq": 4711,
  "state": "IMBALANCE",
  "confidence": 0.93
}
```

### 14.2 MQTT `pdm/{asset_id}/state` (schema v1)

```json
{
  "schema_ver": 1,
  "asset_id": "fan-01",
  "ts_utc": "2026-07-15T14:32:10.123Z",
  "seq": 4711,
  "state": "IMBALANCE",
  "confidence": 0.93
}
```

### 14.3 Flask WebSocket frame

Identical to §14.2.

### 14.4 Error Envelope (REST)

```json
{ "error": { "code": "BAD_RANGE", "message": "to < from", "hint": "use ISO 8601" } }
```

---

## 15. Test & Verification — Acceptance Test Procedures

All ATPs live as runnable scripts where feasible. Each ATP maps to one or more acceptance criteria from §2.2.

### 15.1 Test Levels

| Level | Coverage |
|---|---|
| **Unit** | Python — features, capture parser, schema validators (`pytest`). Firmware — pure-C helpers via host-side build |
| **Integration** | Nano→Pi BLE round-trip; bleak→MQTT→Node-RED→SQLite; Flask→SQLite read; WebSocket push |
| **System** | End-to-end demo per Use Cases 1–3 (charter §4.3) |
| **Acceptance** | ATPs below |

### 15.2 ATPs

#### ATP-01 — On-device inference latency (AC-2)
- **Pre-condition.** Nano flashed with INT8 model; firmware built with `-DDEBUG_TIMING=1`.
- **Procedure.** `make atp01 PORT=/dev/cu.usbmodemXXXX ARGS="--duration-s 60"` — see [`scripts/atp01_timing.py`](scripts/atp01_timing.py).
- **Acceptance.** p95 < 250 ms; p99 < 350 ms. The script exits non-zero if the gate fails.
- **Owner.** Firmware lead.

#### ATP-02 — Nano memory footprint (AC-3)
- **Pre-condition.** Final `model.h` integrated.
- **Procedure.** `make verify-firmware` — runs `arduino-cli compile` and prints the size report.
- **Acceptance.** Flash usage ≤ 70%; SRAM usage ≤ 70%.
- **Owner.** Firmware lead.

#### ATP-03 — BLE link reliability
- **Procedure.** Pi within 3 m line-of-sight; run 30 min; observe the `ATP-03 metric` lines emitted by [`gateway.ble_central.SeqStats`](gateway/ble_central.py) every minute.
- **Acceptance.** ≤ 0.5% missed sequence numbers; no disconnect lasting > 5 s.
- **Owner.** Gateway lead.

#### ATP-04 — Schema conformance
- **Procedure.** `pytest tests/integration/test_schema.py` validates every layer's payload against JSON Schema v1.
- **Acceptance.** 100% pass.
- **Owner.** Gateway lead.

#### ATP-05 — Test-set accuracy (AC-1)
- **Pre-condition.** Frozen `v0.5` dataset.
- **Procedure.** Run `make eval` on held-out test split; record per-class precision/recall and overall accuracy.
- **Acceptance.** Overall accuracy ≥ 90%; per-class recall ≥ 80%.
- **Owner.** ML lead.

#### ATP-06 — Gateway resilience
- **Procedure.** While stack is running, kill `bleak_central` with `kill -9`; systemd restarts it; verify next `state` reaches SQLite within 15 s.
- **Acceptance.** Recovery < 15 s; no DB corruption.
- **Owner.** Gateway lead.

#### ATP-07 — HMI freshness (AC-5)
- **Procedure.** Inject a known state change (swap fault SOP); time from injection to operator tile update.
- **Acceptance.** Update visible within 1 s (p95) on a local LAN browser.
- **Owner.** App lead.

#### ATP-08 — Persistence soak (AC-6)
- **Procedure.** Run full stack 30 min; compare count of MQTT `state` messages received vs `events` rows in SQLite.
- **Acceptance.** Zero unaccounted drops.
- **Owner.** Gateway lead.

#### ATP-09 — Live fault recognition (AC-4)
- **Procedure.** For each fault class, inject per the §9.2 SOP four times in independent trials (operator unaware of expected class until prediction shown). Record predictions.
- **Acceptance.** ≥ 3 of 4 correct per fault class.
- **Owner.** PM oversees; all three members operate one fault.

#### ATP-10 — OEE endpoint sanity (AC-7)
- **Procedure.** Drive a scripted sequence (60 s HEALTHY, 30 s IMBALANCE, 60 s HEALTHY); call `/api/v1/oee?window=180`.
- **Acceptance.** Returned availability within ±5% of expected (≈ 80%).
- **Owner.** App lead.

#### ATP-11 — Demo dry-run (no AC; gates final recording)
- **Procedure.** Execute Demo Script in §16 end-to-end without ad-hoc fixes.
- **Acceptance.** All steps complete; runtime ≤ 7 min.
- **Owner.** PM.

### 15.3 CI

GitHub Actions on every PR: `ruff`, `black --check`, `pytest`, firmware build (arduino-cli) if `firmware/**` changed, model artifact smoke build if `ml/**` changed.

---

## 16. Final Demo Script (Week 10)

Target runtime: **5–7 minutes**. Recorded in one take; one clean dry-run pre-recorded as fallback (R5 mitigation).

| Time | Scene | Action | Voice-over key points |
|---|---|---|---|
| 0:00–0:30 | Title card + system block diagram | Static graphic + voice intro | Project name, team, problem statement (one sentence) |
| 0:30–1:00 | Wide shot of asset on mount with Nano attached | Pan around the rig | Hardware tour: Nano + shield + IMU + asset; ISA-95 L0/L1 |
| 1:00–2:00 | Pi gateway + operator laptop on screen | Show Flask `/` HMI tile = HEALTHY | "Healthy baseline"; mention 90% accuracy figure from §2 |
| 2:00–3:00 | **Inject IMBALANCE** per §9.2.1 SOP | Operator visibly adds mass; HMI flips amber within 1 s | Show Use Case 1 (operator) |
| 3:00–4:00 | Switch to `/trend` view | Show last-5-min trend | Show Use Case 2 (maintenance tech) |
| 4:00–5:00 | **Inject LOOSENESS**, then **BEARING_FAULT** | Each transitions on the HMI | Reinforce that all three faults are detected |
| 5:00–5:45 | Show `/api/v1/oee` JSON in browser | Curl-style call | Show Use Case 3 (reliability engineer); KPI tie-back |
| 5:45–6:30 | Cut to slide: metrics summary | On-screen: accuracy, latency, model size | Acceptance criteria summary |
| 6:30–7:00 | Closing card | Team credits, repo URL | "Source available at github.com/<owner>/VibroSenseEdgeAI" |

**Spare kit on bench during recording (R5):** spare Nano flashed with the same firmware, spare battery, spare Pi SD card with provisioned image.

---

## 17. Risk Register

From charter §10.1, with risk scores (Likelihood × Impact, 1–5 each) and review cadence. Reviewed at the weekly status meeting; PM updates this section.

| # | Risk | L | I | Score | Mitigation | Owner | Next review |
|---|---|---|---|---|---|---|---|
| R1 | Insufficient labeled data / poor fault separability | 3 | 4 | 12 | Lock capture protocol Wk 3; ≥ 30 min/class; RF baseline Wk 4 confirms separability before deep model; widen window or fall back to 2-class | ML lead | Wk 4 |
| R2 | On-device fit fails (memory or battery) | 2 | 3 | 6 | Cap model at 100 KB pre-quant; verify at PDR; sleep between windows; AA pack fallback | Firmware lead | Wk 5 |
| R3 | BLE link unreliable | 3 | 3 | 9 | Short payloads; GATT notify with retry; Pi within 3 m line-of-sight; ATP-03 in Wk 6 | Gateway lead | Wk 6 |
| R4 | Team availability gaps | 4 | 3 | 12 | Two-deep coverage; weekly status pulls; PM escalates within 48 h of missed handoff | PM | Weekly |
| R5 | Live demo failure during final recording | 3 | 4 | 12 | Rehearse Wk 9 (ATP-11); pre-record clean run; spare Nano, battery, Pi SD card on bench | PM | Wk 9 |
| R6 | Train/test distribution mismatch (different fault injection between sessions) | 3 | 4 | 12 | Fault Injection SOPs §9.2; session metadata captures fault parameters; stratify splits by session | ML lead | Wk 4 |
| R7 | Hidden data leakage (same session in train and test) | 2 | 4 | 8 | Stratified-by-session split enforced in `train_cnn.py`; unit-tested | ML lead | Wk 4 |

**Risk-score thresholds.** ≥ 12 = address this week; 6–11 = track in weekly review; ≤ 5 = monitor.

---

## 18. Budget

Charter §9. ISE lab funding requested for most hardware; team self-funds only minor consumables not covered by the lab.

| Item | Unit | Qty | Ext. |
|---|---|---|---|
| Arduino Nano 33 BLE Sense (owned, TinyML kit) | $0 | 1 | $0 |
| Tiny ML Shield (owned) | $0 | 1 | $0 |
| Raspberry Pi 4 (lab-owned gateway) | $0 | 1 | $0 |
| Test asset (basic / smart fan, TBD Wk 2) | ≤ $100 | 1 | ≤ $100 |
| Mounting bracket, tape, fasteners | $10 | 1 | $10 |
| Battery (CR2032 or AA holder) + connector | $8 | 1 | $8 |
| Calibrated mass set (washers, coins) for imbalance | $5 | 1 | $5 |
| Software (FOSS) | $0 | — | $0 |
| Contingency | — | — | $15 |
| **Total (ISE lab funding requested)** | | | **≤ $140** |

Per-line BOM with vendor links locked in Week 2 alongside Test Plan ([OD-05](#24-open-decisions-register)). Team labor (estimated, not billed) ≈ 25 hours per member per week during active integration.

---

## 19. Communication Plan & Decision Log

### 19.1 Meeting cadence

| Meeting | When | Who | Output |
|---|---|---|---|
| **Weekly status** | Mondays, 30 min | All members + PM | Action items in repo issues; risk-register review; exit-gate check for the week |
| **Mid-week sync** | Thursdays, 15 min | All members | Blocker triage |
| **Sponsor check-in** | As scheduled by instructor | PM + sponsor | Decisions logged below |
| **Ad-hoc design review** | Before any ADR is merged | Workstream owner + 1 reviewer | ADR file under `docs/decisions/` |

### 19.2 Channels

- **Repo issues / PRs.** Source of truth for work in flight.
- **Group chat (Slack/Discord/Teams — TBD Wk 1).** Daily async; not authoritative for decisions.
- **Email.** Sponsor / instructor communications only.

### 19.3 Decision Log

Authoritative log of irreversible-or-expensive-to-reverse decisions. New entries are added by PR. Reference ADR numbers where applicable.

| # | Date | Decision | Why | ADR |
|---|---|---|---|---|
| D-001 | TBD | Test asset selection | TBD | — |
| D-002 | TBD | BLE GATT UUIDs | Need stable identifiers across firmware/gateway | ADR-0001 |
| D-003 | TBD | Bearing fault simulation method (A/B/C from §9.2.3) | Lock to one method for reproducibility | ADR-0002 |
| D-004 | TBD | Confidence floor for state transitions | Suppress flicker | ADR-0003 |

---

## 20. Deliverables Checklist

- [ ] Team Charter
- [ ] Project Charter (final v6+)
- [ ] Test Plan (final)
- [ ] **PDR Video** (Week 4) — tagged `v0.4-PDR`
- [ ] **CDR Video** (Week 7) — tagged `v0.7-CDR`
- [ ] **Final Demonstration Video** (Week 10)
- [ ] **Final Project Report** (course formatting: cover page; Times New Roman 12 pt; double-spaced; 1-inch margins; lower-right page numbers; APA citations)
- [ ] **Source code package** — tagged GitHub release `v1.0-Final`
- [ ] Schematics & wiring diagrams (in `docs/schematics/`)
- [ ] Lessons Learned (`docs/lessons-learned.md`)
- [ ] README — build, schema, run procedure

---

## 21. GitHub Workflow

- **Hosting.** `github.com/<owner>/VibroSenseEdgeAI`. PM creates the repo and adds members as collaborators after Week 1 alignment.
- **Branching.** Trunk-based. Feature branches → PR → review by a second team member → merge to `main`. Direct push to `main` is disabled.
- **Reviews.** Every PR reviewed by someone other than the author. PR body uses the template — link to issue, list test evidence.
- **Tags.** Semantic-versioned, one per deliverable checkpoint: `v0.4-PDR`, `v0.7-CDR`, `v1.0-Final`, plus weekly minors as useful.
- **Issues.** Labeled by workstream (`firmware`, `ml`, `gateway`, `app`, `docs`, `infra`). Each issue has an owner and a target week.
- **CI.** GitHub Actions runs lint + pytest + firmware build on every PR (see §15.3).
- **Secrets.** None expected (no cloud). If anything sensitive ever appears, use GitHub Encrypted Secrets — never commit.

### First-week repo setup (post-creation)

```bash
# from inside this folder, once GitHub repo exists
git init
git add .
git commit -m "chore: initial scaffold and project plan"
git branch -M main
git remote add origin git@github.com:<owner>/VibroSenseEdgeAI.git
git push -u origin main
git tag v0.1-scaffold && git push --tags
```

---

## 22. Onboarding — Quick Start

A new team member should be able to go from clone to a running local demo (mock BLE) in **< 30 minutes**.

### 22.1 Dev box prerequisites

- macOS or Linux (Windows + WSL2 also fine)
- Python 3.11 + `pipx`
- Git + Git LFS
- arduino-cli (`brew install arduino-cli` on macOS)
- Node.js LTS (for Node-RED)
- Mosquitto MQTT broker
- VS Code (recommended)

### 22.2 Bootstrap

```bash
git clone git@github.com:<owner>/VibroSenseEdgeAI.git
cd VibroSenseEdgeAI
make setup           # creates venv, installs deps, sets up pre-commit
make test            # full unit test suite
make demo            # runs gateway + app against a real Nano (sister demo repo has the mock path)
open http://localhost:5000
```

### 22.3 Canonical `make` targets

| Target | What it does |
|---|---|
| `make setup` | One-shot dev env setup |
| `make lint` / `make format` | ruff + black check / autofix |
| `make test` | pytest across `ml/`, `gateway/`, `app/`, `tests/` |
| `make capture` | Launch the BLE capture tool against a real Nano (raw_window per ADR-0004) |
| `make synth-dataset` | Generate a synthetic 4-class dataset for pipeline tests (no hardware needed) |
| `make baseline` | Train + report the sklearn RandomForest baseline |
| `make train` | Train the 1D-CNN |
| `make quantize` | INT8 quantize Keras → TFLite |
| `make export` | TFLite → C header at `firmware/nano33/model/model.h` |
| `make eval` | Run ATP-05 evaluation (accuracy, per-class recall, confusion matrix) |
| `make ml-pipeline` | End-to-end ML smoke: synth → train → quantize → export → eval |
| `make firmware` | `arduino-cli compile` the Nano sketch |
| `make verify-firmware` | Strict compile + size report for ATP-02 |
| `make flash` | Flash the connected Nano |
| `make atp01` | Run the ATP-01 timing parser (`-DDEBUG_TIMING=1` flash required) |
| `make merge-sessions` | Concatenate per-session capture parquets into a training dataset + manifest |
| `make demo` | Run the stack against a real Nano (this repo is hardware-targeted; see `../VibroSenseEdgeAI-demo` for the mock path) |
| `make dev-bootstrap` | Provision a fresh laptop (arduino-cli + cores + libs + venv) |
| `make pi-bootstrap` | Provision a fresh Pi 4 (idempotent) |

---

## 23. CLO Traceability Matrix

Maps each ISE 575 Course Learning Objective to deliverables and plan sections so the final report can be written against the rubric.

| CLO | Description | Deliverables | Plan sections |
|---|---|---|---|
| **CLO 1** | Team rules / Team Charter | Team Charter | §7, §19 |
| **CLO 2** | Documented PM plan (charter, test plan, design reviews) | Project Charter; Test Plan; PDR Video; CDR Video | §2, §8, §15, §16, §17, §20 |
| **CLO 3** | Systems view; verification tied to requirements before development | This plan; ATPs in §15 | §3, §4, §14, §15, §23 |
| **CLO 4** | TinyML hardware + sensors + supervisory analytics demonstrating an Industry 4.0 use case | Firmware + gateway + Flask stack; Final Demo Video | §10, §11, §12, §13, §16 |
| **CLO 5** | Functioning mock Industry 4.0 system using the TinyML kit | Final Demo Video; tagged source release | §3, §16, §20 |

---

## 24. Open Decisions Register

Items intentionally unresolved at charter signing. Each has an owner, a target close date, and (once closed) a link to its ADR or decision-log entry.

| ID | Decision | Owner | Target close | Status |
|---|---|---|---|---|
| OD-01 | Test asset (basic desk fan vs smart fan, ≤ $100) | PM + Mechanical | End of Wk 2 | Open |
| OD-02 | Sample rate (ODR) and window size | ML + Firmware | End of Wk 3 | Open |
| OD-03 | BLE GATT service + characteristic UUIDs | Firmware | End of Wk 2 | **Closed 2026-05-23** → frozen in [ADR-0001](docs/decisions/0001-ble-payload-schema.md) |
| OD-04 | Workstream owner assignments (§7.1) | PM | End of Wk 2 | Open |
| OD-05 | Per-line BOM with vendor links | PM | End of Wk 2 | Open |
| OD-06 | Battery: CR2032 vs AA pack | Firmware | End of Wk 3 | Pending power characterization |
| OD-07 | Bearing fault simulation method (A/B/C in §9.2.3) | Mechanical + ML | Wk 3 (before bulk capture) | Open → ADR-0002 |
| OD-08 | Group chat platform (Slack/Discord/Teams) | PM | End of Wk 1 | Open |
| OD-09 | Confidence floor for Node-RED state-change filtering | Gateway | Wk 6 | Open → ADR-0003 |

---

## 25. Glossary & References

### Glossary

| Term | Meaning |
|---|---|
| **TinyML** | Machine learning on resource-constrained microcontrollers |
| **TFLite Micro** | TensorFlow Lite for Microcontrollers — runtime for INT8 quantized models on MCUs |
| **GATT** | Generic Attribute Profile — BLE data-exchange layer |
| **ODR** | Output Data Rate (IMU sample rate) |
| **OEE** | Overall Equipment Effectiveness; this project approximates availability only |
| **MES** | Manufacturing Execution System (ISA-95 Level 3) |
| **ISA-95** | Standard reference architecture for enterprise-control integration (Levels 0–4) |
| **IMU** | Inertial Measurement Unit (accel + gyro + mag) |
| **LSM9DS1** | The 9-axis IMU onboard the Nano 33 BLE Sense |
| **ADR** | Architecture Decision Record — short markdown documenting a non-trivial decision |
| **ATP** | Acceptance Test Procedure — runnable test mapped to an acceptance criterion |
| **CLO** | Course Learning Objective |

### References (internal)

- `../Week01_ProjectCharter_v6.docx` — authoritative charter (source for this plan)
- `../Week01_ProjectPitch_v4.pptx` — pitch deck
- `../Week01/` — supporting Week 1 materials

### References (external, to confirm in Wk 2 when used)

- TensorFlow Lite Micro documentation
- Arduino Nano 33 BLE Sense schematic / datasheet
- LSM9DS1 datasheet
- ISA-95 reference architecture (ISA-95.00.01)
- CWRU Bearing Data Center (pivot dataset per §2.3)

---

*This plan tracks the charter v6 as authoritative. Any divergence between plan and implementation is captured in PRs and rolled up into the Final Report. Plan version: v0.2 — last updated 2026-05-22.*
