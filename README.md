# AgriAgent

AgriAgent looks at a photo of a crop field, finds the weeds, and produces a map of only the weed areas, so a sprayer could treat weeds without spraying the crop. It is a Final Year Project and a **research prototype**. It does not control real spraying equipment.

**Start here:** [docs/AgriAgent_Project_Map.pdf](docs/AgriAgent_Project_Map.pdf). It covers what we are building, what is real today, what we deliver in November, and who owns what.

## How it works

```text
field photo
    │
    ▼
1. Detect    Grounding DINO-tiny   text prompt → boxes
2. Segment   SAM 2-tiny            boxes → pixel masks (+ refinement loop)
3. Gate      DeterministicRouter   keep weed masks only, never crop; suppress if infestation > 85%
4. Escalate  (only when unsure)    Clef Flash triage → Qwen VLM diagnosis → ICAR/CIBRC herbicide lookup
5. Output    Streamlit dashboard + GeoJSON built only from approved weed masks
```

AI models can advise, but only plain, tested Python rules decide what goes on the spray map.

## Status (11 October 2026)

| Part | Status |
|---|---|
| Grounding DINO + SAM 2 | Ran once with real weights on Kaggle. The output wrongly included the crop (see Week 2 dossier) |
| Safety gate and GeoJSON export | Tested with mock data: 175 unit + 35 end-to-end tests, CI green |
| Streamlit app, agronomy reasoning | Code works in mock mode; not yet run with real models |
| Evaluation metrics | No real numbers yet |

## Documents

| File | Purpose |
|---|---|
| [docs/AgriAgent_Project_Map.typ](docs/AgriAgent_Project_Map.typ) | Plan, deliverables, tracks, timeline (source of truth) |
| [docs/AgriAgent_Week1_Dossier.typ](docs/AgriAgent_Week1_Dossier.typ) | What Week 1 built |
| [docs/AgriAgent_Week2_Dossier.typ](docs/AgriAgent_Week2_Dossier.typ) | Week 2 cleanup, safety fix, the real result |

All documents are written in [Typst](https://typst.app). Rebuild a PDF with `typst compile docs/<file>.typ`.

## Repository layout

```text
src/vision/       Grounding DINO and SAM 2 wrappers, refinement, visualisation
src/agents/       DeterministicRouter (safety gate) and Clef Flash triage adapter
src/agronomy/     VLM critic, ICAR knowledge store, herbicide prescription, model providers
src/evaluation/   IoU/Dice metrics, benchmark and ablation runners
src/workflow.py   The pipeline: detect → segment → refine → spray map → triage → System 2
app/              Streamlit dashboard
tests/            Unit tests and tests/e2e end-to-end scenarios
data/             Dataset links, ICAR herbicide bulletin, evaluation manifest (no weights or datasets)
config/           Thresholds and prompts
scripts/          run_live_pipeline.py: run real models on one image
notebooks/        Kaggle GPU notebook
```

## Setup

Use Python 3.10 or 3.11.

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env      # add GROQ_API_KEY for real agronomy reasoning

streamlit run app/app.py                                       # dashboard
python scripts/run_live_pipeline.py --image path/to/field.jpg  # real models on one image
```

Model weights download from Hugging Face on first real run and are never committed.

## Checks (same as CI)

```bash
ruff check . && ruff format --check .
mypy --config-file pyproject.toml src/
PYTHONPATH=. python -m unittest discover tests
PYTHONPATH=. python tests/e2e/runner.py --all
```

Passing tests show the code behaves correctly on test inputs. They do not show model accuracy or field safety.

## Team

| Track | Area |
|---|---|
| 1 · Chaitanya | Core vision, workflow, safety gate |
| 2 · Sumant | Agronomy reasoning and knowledge base |
| 3 · Sahil | Datasets and evaluation |
| 4 · Amit | Streamlit UI, integration, CI |

Guided by Prof. V. D. Dhore · Academic year 2025–26.
