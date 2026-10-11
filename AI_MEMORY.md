# AgriAgent project memory

AgriAgent is a research prototype for image-based vegetation analysis and selective spray-map review. It is not field-ready.

## Current model plan

- Local triage: `Cloudflare/clef-flash`; local cache only at inference.
- Local agronomy/VLM provider: `Qwen/Qwen3.5-4B` through an OpenAI-compatible local service.
- The sole cloud model path: Groq `qwen/qwen3.8-27b`.
- The deterministic safety gate is the final spray authority.

Tests can use synthetic inputs and mock providers. Do not describe those results as live model verification. No GPU/model execution was verified in the last repository review.

See `docs/models_and_runtime.md`, `docs/cleanup_execution_sprint.md`, and `docs/AgriAgent_Week2_Master_Technical_Dossier.typ` for current setup, plan, and evidence status.
