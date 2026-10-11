# Repository audit summary

This note records the current implementation boundaries for cleanup and release review.

## Verified by source inspection

- The workflow is organized in `src/workflow.py`; detection and segmentation are implemented in `src/vision/`.
- The deterministic router is available in `src/agents/deterministic_router.py`.
- Local Clef triage is implemented in `src/agents/clef_flash_router.py` and is intended to load local model files only.
- Agronomy providers include a local endpoint client and a Groq client.
- Spray map construction and GeoJSON export are implemented separately and must preserve the approved-artifact contract.

## Risks requiring validation

- A model confidence score is not independent ground-truth accuracy.
- Mock mode does not establish live inference behavior, quality, or latency.
- The environment inspected did not expose a working NVIDIA driver.
- Placeholder GPS coordinates and software-only suppression checks do not establish actuator safety.
- Agronomy and statutory recommendations require expert review and current source verification.

## Required follow-up

Run the safety regression tests and full CI commands, review historical evaluation artifact provenance, verify local model/runtime compatibility, and complete independent field and hardware validation before making deployment claims.
