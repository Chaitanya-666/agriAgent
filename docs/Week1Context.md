# AgriAgent project context

AgriAgent is a research prototype for field-image analysis and selective weed-management research. The current implementation links Grounding DINO proposals, SAM 2 masks, optional geometric refinement, agronomy providers, and a safety-filtered spray-map artifact.

## Current architecture

1. Grounding DINO proposes candidate regions from an image and text prompt.
2. SAM 2 predicts a mask for each candidate. Optional refinement requests another mask when quality is low.
3. Local Clef Flash may help classify ambiguity. It cannot approve spraying.
4. A deterministic gate checks the approved weed masks and infestation ceiling.
5. The application exports GeoJSON only from the workflow's approved spray-map artifact.

GeoJSON coordinates are research placeholders. The current software is not connected to validated GPS or physical spray hardware.

## Models and evidence

- Local triage model: `Cloudflare/clef-flash`.
- Local agronomy/VLM model: `Qwen/Qwen3.5-4B`.
- Cloud agronomy model: Groq `qwen/qwen3.8-27b`.
- Unit and E2E suites include mock-mode behavior. Mock checks do not establish live model accuracy or runtime.
- GPU execution was not available in the repository review environment.

See [Models and runtime](models_and_runtime.md), [Week 2 evidence dossier](AgriAgent_Week2_Master_Technical_Dossier.typ), and [execution sprint](cleanup_execution_sprint.md) for current setup, evidence, and work items.
