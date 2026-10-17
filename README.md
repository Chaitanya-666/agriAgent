# AgriAgent

AgriAgent looks at a photo of a crop field, finds the plants, and produces a map of only the weed areas, so a sprayer could treat weeds without spraying the crop. It is a Final Year Project and a **research prototype**: it asks how well zero-shot foundation models tell weeds from crop plants, and whether a safety gate plus a reasoning model keeps the crop off the spray map. It does not control real spraying equipment.

**Start here:** [docs/AgriAgent_Progress_Report_Guide.pdf](docs/AgriAgent_Progress_Report_Guide.pdf) (the whole story to 17 October) and [docs/AgriAgent_Team_Tasks.pdf](docs/AgriAgent_Team_Tasks.pdf) (who does what until 21 October).

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

## Status (17 October 2026)

| Part | Status |
|---|---|
| Grounding DINO + SAM 2 on our laptop (RTX 5050) | **Real**: both models run, 2.4 GB peak GPU memory |
| Safety gate with real confidence | **Real**: withholds low-confidence masks on real images; 192 unit + 35 end-to-end tests |
| System 2 with Groq (sees the image) | **Real** diagnosis; real-mode ICAR store not loaded yet, so most prescriptions say "no evidence" |
| Clef Flash (Cloudflare) triage | Answers on its own (14/20 patches); not yet in the workflow |
| Evaluation set | **Real**: `data/manifests/eval_manifest_v2.json`, 38 images with official labels. `eval_manifest_v1` was fabricated and must not be used |
| Evaluation numbers | Crop-or-weed on 20 patches: Groq 16/20, Clef 14/20, row rule 13/20. Full baseline due 25 October |

The main finding so far: text prompts alone do not separate weed from crop (on a sugar beet photo all four crop plants were labelled "weed"). Details and figures in the progress report.

## Documents

| File | Purpose |
|---|---|
| [docs/AgriAgent_Progress_Report_Guide.typ](docs/AgriAgent_Progress_Report_Guide.typ) | Full progress report for the guide: proposal vs today, history, mistakes, evidence, related work, plan |
| [docs/AgriAgent_Team_Tasks.typ](docs/AgriAgent_Team_Tasks.typ) | Step-by-step tasks per member until 21 October |
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
