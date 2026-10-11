# AgriAgent project status

AgriAgent is a research prototype that connects field-image proposals, segmentation masks, agronomy reasoning, and a safety-filtered spray-map artifact.

## Architecture

Grounding DINO proposes candidate regions. SAM 2 predicts masks. Local Clef Flash may recommend ambiguity escalation. `DeterministicRouter` remains the final authority for spray safety. The app exports only approved mask zones from the spray-map artifact.

## Model plan

- Local Clef triage: `Cloudflare/clef-flash`.
- Local agronomy/VLM: `Qwen/Qwen3.5-4B`.
- Cloud: Groq `qwen/qwen3.8-27b` only.

Model weights are not committed. Live model behavior and GPU performance are not yet verified. See `docs/models_and_runtime.md` for setup and limits.

## Work to complete

1. Pass CI on Python 3.10 and 3.11, including mypy, unit tests, end-to-end tests, and Streamlit smoke test.
2. Verify spray exports use only approved masks and fail closed on crop/unsafe labels and high infestation.
3. Verify local Clef and Qwen model/runtime compatibility on target hardware.
4. Review evaluation manifests and generated metrics; identify mock versus live evidence.
5. Complete agronomist review, GPS calibration, field validation, and hardware safety work before any field-ready claim.

The detailed acceptance criteria are in `docs/cleanup_execution_sprint.md`.
