# Known limitations and future work

AgriAgent is a research prototype. Its current tests and interface are not sufficient evidence for autonomous field spraying.

## Current limitations

- Live Clef, Qwen, Grounding DINO, and SAM 2 execution was not verified in the last repository review.
- The checked environment did not have a working NVIDIA driver, so no GPU availability or performance claim can be made.
- Unit and end-to-end checks can use mock providers, synthetic images, and deterministic fixtures.
- GeoJSON coordinates are placeholders; no surveyed GPS transform or hardware interface has been validated.
- Weed/crop label policy, segmentation quality, chemical recommendations, and infestation thresholds need independent agronomy review.
- Model serving compatibility and memory use depend on specific model revisions, quantization, framework versions, input resolution, and context size.

## Future work before any field deployment

1. Run pinned local model revisions on named hardware and publish reproducible evaluation artifacts.
2. Evaluate detection and segmentation against reviewed ground-truth data, including difficult crop/weed overlap cases.
3. Validate the label taxonomy and chemical guidance with qualified agronomists and applicable regulatory sources.
4. Calibrate image coordinates to surveyed field coordinates and validate nozzle timing under controlled conditions.
5. Add independent hardware interlocks, emergency stop behavior, and fault-injection tests.
6. Complete supervised field trials and a safety review before considering autonomous use.

## Current boundaries

Local Clef and Qwen are the intended on-device models. Groq `qwen/qwen3.8-27b` is the only cloud model. Local models require weights and a supported runtime; inference does not silently change to mock mode. Groq requires a key and a network connection. See `models_and_runtime.md` for configuration and approximate memory planning.
