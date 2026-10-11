#set document(title: "AgriAgent Week 2 Evidence Dossier", author: "AgriAgent Team")
#set page(paper: "a4", margin: 2cm)
#set text(font: "Libertinus Serif", size: 10pt)
#set heading(numbering: "1.")

= AgriAgent Week 2 Evidence Dossier

*Review date:* 11 October 2026  \
*Scope:* repository implementation and checks available in this checkout  \
*Status:* in progress; this report does not certify field readiness.

== Project summary

AgriAgent is a research prototype that processes field images, creates candidate vegetation masks, runs agronomy reasoning, and prepares spray-map artifacts for review. A deterministic gate owns spray safety. Local Clef Flash can assist ambiguity triage but cannot authorize spraying.

The intended models are local `Cloudflare/clef-flash`, local `Qwen/Qwen3.5-4B`, and cloud-only Groq `qwen/qwen3.8-27b`. Local model execution has not been verified in this environment. Tests using `mock_mode=True` verify software contracts, not model quality.

== Evidence matrix

#table(
  columns: (1.05fr, 0.7fr, 1.65fr, 1.7fr),
  inset: 5pt,
  stroke: 0.5pt,
  [*Area*], [*Status*], [*Evidence*], [*Remaining work*],
  [Vision pipeline], [Partial], [`src/workflow.py`, `src/vision/grounding_dino.py`, `src/vision/sam2_wrapper.py`; mock/unit workflow tests.], [Run with pinned real weights and independently annotated field images; review errors and calibration.],
  [Spray safety], [Repository contract verified], [`src/workflow.py`, `app/components/pipeline.py`, `tests/test_spray_export_safety.py`; six safety regressions pass, including crop rejection, grass acceptance, suppression, raw-box rejection, and mask-derived geometry.], [Review every label policy and physical suppression threshold with an agronomist and hardware team; validate GPS calibration and actuators.],
  [Local Clef], [Implemented; runtime unverified], [`src/agents/clef_flash_router.py` uses local cache-only loading and escalation on load failure.], [Install model/runtime, verify image processor compatibility, memory, triage quality, and offline startup on target hardware.],
  [Local Qwen3.5-4B], [Partial], [`src/agronomy/providers/local_qwen.py`, `src/agronomy/vlm_critic.py`, provider mock tests.], [Confirm serving stack compatibility and run a live local diagnosis with recorded model revision and device.],
  [Groq Qwen3.8-27B], [Partial], [`src/agronomy/providers/hosted_groq.py` defaults to requested model; provider mock/config tests.], [Verify model availability and response schema using an authorized live API key.],
  [Evaluation], [Mock and manifest-based code], [`src/evaluation/ablation_runner.py`, `data/manifests/eval_manifest_v1.json`; mock-mode runs do not measure model performance.], [Review labels/splits and rerun real models; retain provenance, revisions, device, and output metadata.],
  [CI], [Local checks pass; target matrix pending], [Python 3.14: compileall, Ruff check/format, mypy (27 source files), 175 unit tests, and 35 E2E tests pass. Python 3.10 is not installed here; Python 3.11 lacks project test dependencies. Streamlit is unavailable locally.], [Confirm Python 3.10/3.11 GitHub Actions results and headless Streamlit health check in a dependency-complete environment.],
  [Documentation], [Mostly updated; final review pending], [`README.md`, `docs/models_and_runtime.md`, `docs/cleanup_execution_sprint.md`, Week 1 sources, this dossier; updated PDFs regenerated with Typst.], [Review active documentation and generated PDFs after the final CI matrix.],
)

== Safety contract

Grounding DINO proposals may prompt SAM 2 but are not spray instructions. The workflow filters mask labels, forms an approved spray-map artifact, and applies the deterministic infestation gate. A suppressed result must carry no approved zones. GeoJSON must read only those artifact zones; it must not reconstruct polygons from raw detector boxes.

The current coordinates are illustrative placeholders. This repository has no verified GPS calibration, nozzle hardware integration, vehicle interlocks, or field safety case. No generated GeoJSON is approved for real equipment.

== Checks required for release

Run from the repository root:

```text
python -m compileall src/ app/ tests/
ruff check .
ruff format --check .
mypy --config-file pyproject.toml src/
PYTHONPATH=. python -m unittest discover tests -v
PYTHONPATH=. python tests/e2e/runner.py --all
```

CI additionally runs a headless Streamlit health check. In this checkout the listed local checks passed on Python 3.14; Streamlit was not installed. Python 3.10 and 3.11 matrix results remain pending and must come from GitHub Actions.

== Limitations

- The current environment did not expose a working NVIDIA driver; GPU use and live inference are unverified.
- Approximate memory planning is in `docs/models_and_runtime.md`; it is not a measured benchmark.
- Unit and end-to-end tests can use synthetic inputs and mocked model responses.
- The prototype is not field-ready. Model quality, agronomic correctness, calibration, regulatory review, network/service operation, and physical actuation all need separate validation.

For the detailed task breakdown and acceptance criteria, see `docs/cleanup_execution_sprint.md`.
