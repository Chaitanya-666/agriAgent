# AgriAgent handoff notes

AgriAgent is a research prototype for field-image analysis and spray-map review. The current target is local Clef Flash triage, local Qwen3.5-4B agronomy reasoning, and Groq Qwen3.8-27B as the only cloud model.

The deterministic router remains the final spray safety gate. GeoJSON must come from approved mask zones in the workflow artifact. Do not claim field readiness, live model quality, or GPU performance without direct evidence.

Next work is listed in `docs/cleanup_execution_sprint.md`; runtime setup and verification limits are in `docs/models_and_runtime.md`.
