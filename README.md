# AgriAgent

AgriAgent is a research prototype for detecting vegetation in field images, segmenting candidate plants, and producing a selective spray map for review. It is not a field-ready autonomous sprayer.

## What is implemented

- A vision workflow connecting Grounding DINO, SAM 2, optional mask refinement, and a deterministic spray safety gate.
- A Streamlit interface that can run with synthetic/mock components or configured model providers.
- A local agronomy provider interface, an optional local Qwen3.5-4B endpoint, and a Groq provider configured for `qwen/qwen3.8-27b`.
- A local Clef Flash triage adapter. It can recommend escalation but cannot approve physical spraying.
- Spray GeoJSON built only from approved mask zones placed in the workflow's spray-map artifact. Raw detector boxes are not an export input.

Mock-mode tests exercise contracts and synthetic inputs. They do not verify live model quality, GPU performance, field safety, or agronomic validity. See [Models and runtime](docs/models_and_runtime.md) and [Known limitations](docs/known_limitations_and_future_work.md).

## Safety flow

```text
Grounding DINO + SAM 2
        |
        v
local Clef Flash triage when needed
        |
        v
Deterministic safety gate
        +--> ACCEPT only if safe
        +--> REFINE if mask quality is poor
        +--> ESCALATE_SYSTEM2 when uncertain
        +--> SUPPRESS_SPRAY when unsafe
```

The deterministic gate remains the final authority. A model response alone never authorizes spray actuation. The current GeoJSON uses illustrative plot coordinates and must not be sent to real equipment.

## Quick start

Use Python 3.10 or 3.11. Install the project and run the app:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
streamlit run app/app.py
```

Model weights are downloaded separately and are not stored in Git. Provider variables are listed in [.env.example](.env.example). Local hardware setup and startup commands are in [Models and runtime](docs/models_and_runtime.md).

## Verification

CI checks formatting, lint, syntax, typing, unit/contract tests, mock end-to-end tests, and a headless Streamlit startup. Passing those checks demonstrates code-level behavior only. It does not establish field readiness.

Historical SmartDesk material was the starting point for the original scaffold. It is not part of the current AgriAgent runtime.
