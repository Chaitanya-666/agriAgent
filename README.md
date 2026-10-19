# AgriAgent

AgriAgent looks at a photo of a crop field, finds the plants, and produces a map of only the weed areas, so a sprayer could treat weeds without spraying the crop. It is a Final Year Project and a **research prototype**: it asks how well zero-shot foundation models tell weeds from crop plants, and whether a safety gate plus a reasoning model keeps the crop off the spray map. It does not control real spraying equipment.

**Start here:** [docs/AgriAgent_Progress_Report_Guide.pdf](docs/AgriAgent_Progress_Report_Guide.pdf) (the whole story to 17 October) and [docs/AgriAgent_Team_Tasks.pdf](docs/AgriAgent_Team_Tasks.pdf) (team tasks and test cycle 1, due 27 October) and [docs/AgriAgent_Week4_Dossier.pdf](docs/AgriAgent_Week4_Dossier.pdf) (latest results).

## How it works

```text
field photo + crop name
    │
    ▼
1. Detect    Grounding DINO-tiny (local GPU)   prompt "weed . <crop> plant ." → boxes with label + confidence
2. Segment   SAM 2-tiny (local GPU)            boxes → pixel masks + predicted quality; corrective point if quality < 0.85
3. Gate      DeterministicRouter (rules)       spray a mask only if: weed label (no crop words), confidence ≥ 0.70,
                                               quality ≥ 0.85; suppress the whole map above 85% infestation
4. Escalate  System 2 (Groq, cloud)            when unsure: qwen3.8-27b looks at the photo; herbicide only from the
                                               ICAR table row for the declared crop, otherwise "no evidence"
5. Output    Streamlit app + GeoJSON           REAL/MOCK banner, approved zones only, placeholder (not GPS) coordinates
```

AI models can advise, but only plain, tested Python rules decide what goes on the spray map.

## Status (20 October 2026, feature freeze from 22 October)

| Part | Status |
|---|---|
| Grounding DINO + SAM 2 on our laptop (RTX 5050) | **Real**: 0.56 s per image after warm-up |
| Safety gate | **Real**: real confidence, label policy, whole-photo masks withheld, crop exclusion |
| Rule-based plant classifier (`src/vision/plant_candidates.py`) | **Real**: on 90 held-out sugar beet photos, weed recall 1.8% → 77.9% with 8.8% of crop pixels sprayed; cotton 10.4% |
| Escalation agent (`src/agents/escalation_agent.py`) | **Real**: never approved spraying a crop plant, but added no weed recall (RQ2) |
| System 2 with Groq + ICAR table | **Real**: diagnosis from the photo; herbicide rows checked against the bulletin |
| Farmer summary (English / Hindi / Marathi) | **Real** in real mode; template in mock mode |
| Evaluation sets | `eval_manifest_v2.json` (38 images) and `eval_manifest_v2_holdout.json` (90 images), official labels only |

All numbers and the commands that produced them are in [docs/results/](docs/results/). Main finding: text prompts alone do not separate weed from crop; foundation models plus simple, explainable rules do, on sugar beet.

## Documents

| File | Purpose |
|---|---|
| [docs/AgriAgent_Progress_Report_Guide.typ](docs/AgriAgent_Progress_Report_Guide.typ) | Full progress report for the guide: proposal vs today, history, mistakes, evidence, related work, plan |
| [docs/AgriAgent_Team_Tasks.typ](docs/AgriAgent_Team_Tasks.typ) | Team tasks and test cycle 1 (ST-01…22, VT-01…13, RT-01…05), version 2 |
| [docs/AgriAgent_Week4_Dossier.typ](docs/AgriAgent_Week4_Dossier.typ) | Week 4: baseline, improvements, held-out test, escalation answer, feature freeze |
| [docs/AgriAgent_Week3_Dossier.typ](docs/AgriAgent_Week3_Dossier.typ) | Week 3: first real run, label audit, fixes, bugs closed |
| [docs/AgriAgent_Project_Map.typ](docs/AgriAgent_Project_Map.typ) | Plan, deliverables and frozen decisions (with the 17 October update) |
| [docs/AgriAgent_Schedule.typ](docs/AgriAgent_Schedule.typ) | Week-by-week schedule to the submission on 10 November |
| [docs/AgriAgent_Week1_Dossier.typ](docs/AgriAgent_Week1_Dossier.typ), [Week 2](docs/AgriAgent_Week2_Dossier.typ) | History of Weeks 1 and 2 |
| [docs/testing/](docs/testing/) | Test runbooks |
| [docs/guides/](docs/guides/) | Study guides: 0 Start Here, 1 Concepts, 2 Codebase Walkthrough (known issues K1–K12), 3 Viva Defence, 4 Demo Playbook |

All documents are written in [Typst](https://typst.app). Rebuild a PDF with `typst compile docs/<file>.typ` (guides: `typst compile --root docs docs/guides/<file>.typ`).

## Repository layout

```text
src/vision/       Grounding DINO and SAM 2 wrappers (real mode fails loudly, never falls back to mock), refinement
src/agents/       DeterministicRouter (safety gate rules) and the Clef Flash triage adapter
src/agronomy/     VLM critic (Groq by default), ICAR knowledge store, crop-checked herbicide prescription
src/evaluation/   IoU/Dice metrics, benchmark and ablation runners
src/workflow.py   Pipeline, default_prompt(), label_policy(), spray_status(); detect → segment → refine →
                  spray map → triage → System 2
app/              Streamlit dashboard and GeoJSON export
scripts/          Command-line tools (below)
tests/            Unit tests; tests/e2e end-to-end scenarios
data/             Manifests, ICAR bulletin, dataset links; downloaded datasets go to data/datasets/ (not in git)
config/           Thresholds and prompts
```

## Scripts

| Command | What it does |
|---|---|
| `python scripts/check_providers.py` | Checks that Groq and Cloudflare answer with your `.env` keys |
| `python scripts/run_live_pipeline.py --image F --crop cotton` | Real models on one image; prints the mode used, every mask and whether it was sprayed; saves a 4-panel figure |
| `python scripts/build_eval_manifest_v2.py` | Downloads the official labels and images (about 110 MB, needs a Kaggle token) and writes `eval_manifest_v2.json` |
| `python scripts/show_manifest_labels.py` | Draws the manifest boxes on each image for checking by eye |
| `python scripts/audit_eval_manifest.py` | Compares `eval_manifest_v1` with the official labels (why v1 was dropped) |
| `python scripts/compare_crop_or_weed.py` | Asks Groq, Clef Flash and a row rule "crop or weed?" on 20 labelled patches |
| `python scripts/verify_cycle0_issues.py [--real]` | Re-runs the Cycle 0 failing test cases by driving the app headlessly |
| `python scripts/run_baseline.py [--manifest M] [--agent] [--exclusion]` | Real run over an evaluation set; scores every gate setting and the plant rules against the official labels |

## Setup

Use Python 3.10–3.12.

```bash
python -m venv .venv && source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
cp .env.example .env      # add your Groq key (and Cloudflare for Clef Flash); never commit .env
python scripts/check_providers.py

streamlit run app/app.py                                 # dashboard (Mock Mode on by default)
```

Real mode downloads Grounding DINO-tiny and SAM 2-tiny (about 1.6 GB) from Hugging Face on the first run. A Kaggle token (`~/.kaggle/access_token`) is needed only to download the evaluation data.

## Checks (same as CI)

```bash
ruff check . && ruff format --check .
mypy --config-file pyproject.toml src/
PYTHONPATH=. python -m unittest discover tests
PYTHONPATH=. python tests/e2e/runner.py --all
```

Passing tests show the code behaves correctly on test inputs. They do not show model accuracy or field safety.

## Team

| Member | Role |
|---|---|
| Chaitanya Shinde | Track 1: vision, workflow, safety gate; integration, evaluation runs, report |
| Sumant Vetal | Track 2: agronomy; system tester; report content |
| Sahil Chavan | Track 3: data and evaluation; validation tester |
| Amit Ingle | Track 4: app and demo; tester |

Guided by Prof. V. D. Dhore · Department of Computer Engineering, VJTI · 2026.
