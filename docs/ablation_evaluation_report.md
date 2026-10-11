# Evaluation status and interpretation

The repository contains an evaluation harness and frozen evaluation manifest. Results must be interpreted according to the mode and metadata used for each run.

## What the harness can check

- Dataset-manifest loading and mask metric calculations.
- Vision workflow behavior when mock components are selected.
- Refinement parameter sweeps and deterministic spray safety contracts.
- Provider and router interfaces using explicit mock responses.

These are software checks. Mock router timings are Python/mock-path timings and are not Clef model benchmarks. Synthetic input behavior does not establish field accuracy.

## Evidence required for a live evaluation

Record the manifest revision, image and annotation identifiers, model repository and revision, inference framework/version, device, precision or quantization, mock flag, output artifact, and exact command. Report per-image and aggregate metrics, including failure cases. Keep predicted mask confidence separate from IoU against human annotations.

## Current limits

The present repository review did not run Clef, Qwen, SAM 2, or Grounding DINO on live GPU weights. Existing evaluation JSON files may contain historical outputs produced by earlier adapters; they are not evidence for the current model plan. Review their provenance before using or publishing any value.

Do not publish latency, accuracy, savings, or reliability claims without a reproducible artifact and documented evaluation mode.
