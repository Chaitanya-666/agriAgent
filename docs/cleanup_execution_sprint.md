# AgriAgent cleanup and model migration sprint

This plan records the intended work and acceptance checks for moving the repository to a consistent, reviewable state. It is written for contributors who have not followed the migration discussion.

## Project vision

AgriAgent is a research prototype that turns a field image into candidate vegetation masks, agronomy guidance, and a spray-map artifact for human review. The long-term research goal is selective weed management. The current code and tests do not establish safe autonomous field spraying.

## Current target architecture

```text
Field image
    |
    v
Grounding DINO -> SAM 2 -> optional geometric mask refinement
    |                                      |
    +---- ambiguous case -> local Clef Flash triage
                                           |
                                           v
                            Deterministic safety gate
                  ACCEPT / REFINE / ESCALATE_SYSTEM2 / SUPPRESS_SPRAY
                                           |
                                           v
                       approved spray-map artifact -> GeoJSON
```

Only approved zones derived from workflow masks may be exported. Detector boxes may guide segmentation but must never independently create an actuation feature. Clef Flash can recommend escalation. Only the deterministic gate can approve or suppress a spray map.

## Model decisions

- Local triage: `Cloudflare/clef-flash`, loaded from local files. Do not use Cloudflare's hosted inference service or require Cloudflare credentials.
- Local agronomy/VLM: `Qwen/Qwen3.5-4B`, served through a local OpenAI-compatible endpoint.
- Cloud agronomy provider: Groq `qwen/qwen3.8-27b`. This is the only cloud model path.
- Explicit mock mode is for tests. A mock result must never be presented as a live model result.
- No model weights belong in Git.

## Work tracks and ownership

| Track | Owner | Work | Acceptance |
|---|---|---|---|
| Repository and dependencies | Maintainer | Remove the retired router dependency, reviewed generated artifacts, duplicate files, and historical planning directories. Preserve datasets, fixtures, statutory PDF, research papers, notebooks, and meaningful Typst sources. | Search of active code and docs contains no retired integrations. Protected research/data remains present. Dependency lock strategy is recorded. |
| Router migration | Vision lead | Use local Clef for ambiguity triage where needed; keep `DeterministicRouter` as physical safety authority; remove old compatibility names. | Router tests cover deterministic outcomes and local-runtime failure escalation. No model path can independently approve spraying. |
| Spray safety and application | Safety/UI lead | Make spray-map artifact the only source for export features; filter crop and unsafe labels; handle `grass` consistently; suppress high infestation. | Regression tests show crop labels, crop-name labels, raw boxes, and suppressed maps produce no features; approved weed masks do. |
| Provider/runtime | Model lead | Configure the three model names and environment variables; document install/startup, local cache behavior, resource needs, and errors. | Mock tests pass; live tests are clearly separate and report model/device metadata. No weights committed. |
| Data and evaluation | Evaluation lead | Review manifests, masks, ablations, and saved JSON results. Label mock, live, and external evidence correctly. Re-run only against traceable manifests. | Every reported metric points to an artifact and input manifest; mock adapter measurements are not called model benchmarks. |
| CI/CD | Release lead | Repair mypy issues without broad category suppression; run Python 3.10 and 3.11 CI; use non-fail-fast matrix for diagnosis. | Required local commands pass; CI matrix reports each interpreter; Streamlit smoke test starts if dependencies are available. |
| Documentation | Documentation lead | Replace contradictory README/model/runtime/Week 2 docs; simplify Week 1; retain references and source material; create this sprint record. | Docs state implemented, mocked, unverified, unfinished, and field-readiness limits plainly. |

## Tasks

### Router migration

1. Remove the former third-party router dependency, implementation, exports, and dedicated tests/ablations.
2. Rename workflow constructor/state references to neutral `router` terminology.
3. Implement local Clef loading with cache-only runtime behavior and a clear missing-dependency/weights error.
4. Keep Clef's output advisory. Route mask quality and infestation decisions through deterministic rules.
5. Ensure uncertainty or Clef runtime failure escalates rather than accepting a spray decision.

### Spray-safety contract

1. Identify the masks that pass explicit weed-label checks.
2. Build approved spray zones from those mask pixels and attach them to the spray-map artifact.
3. Run the deterministic infestation ceiling check. For `SUPPRESS_SPRAY`, clear all exportable zones.
4. Have GeoJSON read only artifact zones, never `boxes`.
5. Test crop labels, labels containing crop terms, accepted weeds, `grass`, high infestation, and malicious raw boxes.

### Provider/runtime and evaluation

1. Set the local Qwen default and Groq model exactly once in configuration.
2. Keep cloud credentials optional until live Groq is selected; missing credentials must not fabricate a live response.
3. Document CPU/GPU setup, model downloads, offline behavior, and runtime limitations.
4. Keep mock results distinct from local live model and cloud live model results in output metadata.
5. Do not report hardware timings unless the model actually ran on the named hardware.

### CI/CD

1. Inspect every Layer 2 mypy error and correct annotations, narrowing, or return types at the source.
2. Do not disable whole mypy error categories to get a green build.
3. Run both Python versions independently with `fail-fast: false`.
4. Execute unit tests, the E2E runner, and a headless Streamlit health check.

## Dependency lock strategy

The repository does not currently track `uv.lock`: CI and contributor setup use pip and editable project installation. If the team adopts uv as the supported dependency manager, add and maintain a tracked lockfile as part of that migration; do not rely on an ignored local lock.

### Documentation and repository cleanup

1. Remove the historical SmartDesk copy after confirming no runtime imports point to it; retain the short history note in README.
2. Replace the old Qwen dossier with `docs/models_and_runtime.md`.
3. Verify exact duplicate source/PDF hashes before collapsing duplicate Week 1 files.
4. Keep meaningful Typst sources, papers, data, fixtures, manifests, the statutory knowledge PDF, and notebooks.
5. Remove only ignored, reproducible build/cache artifacts after reviewing exact paths. Keep `.env` untouched and never add model weights.
6. Review `uv.lock`; retain it only if the repository adopts uv as a supported dependency workflow and state that in developer documentation.

## Commands to run

```bash
python -m compileall src/ app/ tests/
ruff check .
ruff format --check .
mypy --config-file pyproject.toml src/
PYTHONPATH=. python -m unittest discover tests -v
PYTHONPATH=. python tests/e2e/runner.py --all
```

The CI workflow also starts Streamlit and checks `/_stcore/health`. Run that smoke test locally when Streamlit is installed. Run any live model check separately and record model id, runtime, device, weight revision, and whether mock mode was disabled.

## Known blockers and boundaries

- Local GPU availability and model execution must be checked on the target machine; this checkout environment did not expose a working NVIDIA driver.
- The specific inference-server versions needed for the Qwen and Clef model revisions must be confirmed against their model implementations.
- The GeoJSON coordinates are research placeholders, not surveyed GPS or actuator-ready nozzle commands.
- Field evaluation, agronomist review, calibration, fail-safe hardware validation, and legal/regulatory approval remain unfinished.

## Definition of done

- CI passes on Python 3.10 and 3.11, including type checking, unit/E2E tests, and Streamlit smoke test.
- GeoJSON is generated only from approved workflow mask artifacts; unsafe or suppressed state emits zero spray features.
- No active source or current documentation references removed model integrations or old model defaults.
- Docs distinguish mock evidence from live model evidence and do not claim field readiness.
- Reviewed repository cleanup is committed on `codex/cleanup-model-migration`; the branch is pushed and a PR is opened only after checks pass.

## Must not change

- Do not overwrite `main` or discard pre-existing local edits.
- Do not delete `.env`, research papers, references, statutory knowledge, meaningful datasets, fixtures, evaluation manifests, or notebooks without review.
- Do not commit model weights or invent model performance results.
- Do not bypass the deterministic spray safety gate or permit a generative model to be the sole actuation authority.
