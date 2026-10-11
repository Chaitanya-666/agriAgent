# AgriAgent E2E Testing Track Infrastructure & Architecture (TEST_INFRA.md)

## 1. Executive Summary & Test Philosophy

### 1.1 Opaque-Box, Requirement-Driven Testing Paradigm
AgriAgent is a dual-system robotic agronomy platform operating under mission-critical agricultural constraints. System 1 executes fast real-time reflex perception (<40 ms) on edge hardware, while System 2 performs deliberative agronomic reasoning over statutory ICAR/CIBRC corpora.

The End-to-End (E2E) testing track strictly adheres to an **opaque-box, requirement-driven testing paradigm**:
1. **Black-Box Observable Verification**: Tests interact with the system strictly through public entry points (`VisionWorkflowRunner`, `StateGraph`, `KnowledgeStore`, `get_herbicide_prescription`, and UI/CLI runner interfaces) and evaluate observable outputs (exit codes, state dictionaries, masks, GeoJSON spray maps, structured prescriptions).
2. **Requirement-Driven Truth**: Assertions are derived exclusively from specifications in `PROJECT.md` and `ORIGINAL_REQUEST.md`, mathematical physical properties (e.g., set theory for IoU/Dice, geometric coordinate bounds, conservation of area for herbicide savings), and statutory regulatory limits (CIBRC maximum residue limits and approved active ingredients).
3. **No Facade or Tautological Tests**: Tests never mirror internal code shortcuts or pass unconditionally. Every test must be capable of failing if the underlying agronomic or vision logic is broken or mutated.
4. **Implementation Decoupling**: Tests are written against interface contracts rather than private class details. If internal algorithms change (e.g., switching from bounding-box subtraction to morphological contour refinement), contract-abiding tests remain valid.

### 1.2 Progressive Testability & Milestone Decoupling
To maintain continuous integration throughout the 6-milestone development lifecycle:
- **Milestone Isolation**: Tests for early milestones verify features up to the current milestone and gracefully degrade or mock unintegrated downstream modules.
- **Dual-Mode Execution**:
  - **Mock / Offline Mode**: Uses deterministic synthetic data generators and pure-Python fallbacks to enable instantaneous, reproducible execution in CPU-only, network-isolated environments (e.g., standard developer laptops, GitHub Actions runners without GPUs).
  - **Live / Hardware Mode**: Exercises actual deep learning backbones (Grounding DINO, SAM 2, local Qwen3.5-9B, or hosted Groq) when hardware accelerators and API credentials are provided.
- **Zero-Dependency Fallbacks**: Tests explicitly verify that missing optional packages (such as `laya`, `chromadb`, or `torch`) trigger safe, documented fallback paths without catastrophic failure.

### 1.3 Test Independence & Isolation
- Each test is strictly isolated: test fixtures create self-contained inputs, isolated temporary directories, and in-memory data structures.
- Tests do not rely on execution order or shared mutable global state.
- All temporary filesystem artifacts are registered with cleanup handlers.

---

## 2. Feature Inventory Mapping Matrix

The 18 features defined in `PROJECT.md` are mapped across the 4 E2E test tiers and test suites:

| # | Feature Name | Description | Target Milestone | E2E Test Tier | Test Module / Verification Target |
|---|--------------|-------------|------------------|---------------|-----------------------------------|
| 1 | Repository Audit & Dossier Reconciliation | Discrepancy tracking, 0.99 IoU audit, Laya text-only verification | M1 | Tier 1, Tier 2 | `tests/e2e/test_tier1_feature_coverage.py` (Laya fallback contract) |
| 2 | Ground-Truth Dataset & Manifests | Versioned evaluation dataset, held-out cotton & sugarbeet splits | M1 | Tier 1 | `tests/e2e/test_tier1_feature_coverage.py` (Real fixture execution) |
| 3 | Independent Vision Evaluation Harness | Calculation of ground-truth IoU, Dice, Precision, Recall, and mAP | M1 | Tier 1, Tier 4 | `tests/e2e/test_tier1_feature_coverage.py` (Evaluation metrics math) |
| 4 | Geometric Mask Refinement Fix | Morphological contour/gradient refinement replacing bbox subtraction | M2 | Tier 1, Tier 2 | `tests/e2e/test_tier1_feature_coverage.py` (Active closed-loop refinement) |
| 5 | Full LangGraph StateGraph & Cyclic Loopback | Cyclic refinement recursion & System-2 integration in StateGraph | M2 | Tier 1, Tier 3 | `tests/e2e/test_tier1_feature_coverage.py` (Workflow DAG execution) |
| 6 | Router Architecture & Clef Flash Comparison | Standardized routing contracts (Deterministic vs Laya vs Clef Flash) | M2 | Tier 2, Tier 3 | `tests/e2e/test_tier2_boundary_robustness.py` (Router fallback triage) |
| 7 | Table-Aware Ingestion & Rich Metadata | Structured ICAR table parsing with crop, AI, and dosage metadata | M3 | Tier 2, Tier 3 | `tests/e2e/test_tier2_boundary_robustness.py` (Knowledge ingestion bounds) |
| 8 | Distance-Gated Retrieval & Safe Fallback | Similarity distance threshold for safe `no_knowledge_found` | M3 | Tier 1, Tier 2 | `tests/e2e/test_tier1_feature_coverage.py`, `test_tier2_boundary_robustness.py` |
| 9 | Statutory Safety & Dosage Ceiling Filter | Enforce CIBRC banned chemical filter and dosage rate upper bounds | M3 | Tier 2, Tier 4 | `tests/e2e/test_tier2_boundary_robustness.py` (Adversarial prescription tests) |
| 10 | Unified LLM/VLM Provider Interface | Configurable contract (`BaseAgronomyProvider`) for Qwen / Groq | M3 | Tier 3 | `tests/e2e/test_tier1_feature_coverage.py` (System-2 diagnosis contract) |
| 11 | Streamlit UI Pipeline Integration | Connect `app/app.py` to `VisionWorkflowRunner` with Mock/Live toggles | M4 | Tier 1, Tier 2 | `tests/e2e/test_tier1_feature_coverage.py` (Runner state compatibility) |
| 12 | Layered GitHub Actions CI/CD | 10-layer quality pipeline (linting, types, unit, contract, E2E) | M4 | All Tiers | Full suite test discovery via `python3 -m unittest discover tests/e2e -v` |
| 13 | Build System & Dependency Standardization | `pyproject.toml`, `.env.example`, missing dependency resolution | M4 | Tier 2 | `tests/e2e/test_tier2_boundary_robustness.py` (Missing dependency resilience) |
| 14 | Reproducible Kaggle GPU Runner & CLI | `kernel-metadata.json`, notebook imports from `src/`, CLI execution | M5 | Tier 1, Tier 4 | `tests/e2e/test_tier1_feature_coverage.py` (Batch execution & metrics) |
| 15 | Controlled Vision & Routing Ablations | Controlled runs for ablations A-E with latency & savings stats | M5 | Tier 1, Tier 4 | `tests/e2e/test_tier1_feature_coverage.py` (Ablation config invariance) |
| 16 | End-to-End System Integration & Contract Validation | Full pipeline from image upload to spray map and RAG diagnosis | M5 | Tier 1, Tier 3 | `tests/e2e/test_tier1_feature_coverage.py` (Complete System-1/2 state validation) |
| 17 | Comprehensive E2E Test Suite (Tiers 1-4) | Opaque-box requirement-driven test suite with >=11*N tests; `TEST_READY.md` | E2E | All Tiers | E2E test harness infrastructure, `tests/e2e/runner.py`, and test suites |
| 18 | Release Candidate & Deliverables Verification | Final documentation, setup guides, release checklist, victory audit | M6 | All Tiers | Master test runner passing with zero regressions |

---

## 3. Four-Tier Testing Methodology & Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AgriAgent E2E Test Track                        │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 1: Feature Coverage (Core Happy Path & State Contracts)          │
│    - End-to-end vision pipeline (Image -> Box -> Mask -> Spray Map)   │
│    - Real field image fixtures (Cotton & Sugarbeet samples)            │
│    - Dual-Brain StateGraph transition verification                     │
│    - Safe no-knowledge fallback on unknown agronomy queries            │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 2: Boundary, Robustness & Fault Tolerance                        │
│    - Empty / 0-byte images, blank canvas, 1x1 pixels, extreme ratios  │
│    - Corrupt image payloads & missing files                            │
│    - Missing optional dependencies (laya, chromadb, torch, cv2)        │
│    - Saturated field infestation (100% weeds -> spray suppression)     │
│    - Zero-infestation field (0% weeds -> 100% herbicide savings)       │
│    - Deterministic spray map mathematical invariants                   │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 3: Interface Contracts & Cross-Module Integration                │
│    - Pydantic/TypedDict state schema validation (`GraphState`)         │
│    - Router contract decisions (ACCEPT, REFINE, ESCALATE, SUPPRESS)    │
│    - Unified Agronomy Provider requests and structured responses       │
│    - Prescription schema compliance & citation traceability            │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 4: Adversarial Verification, Safety Guardrails & Stress          │
│    - Banned pesticide injection & toxic dosage interception            │
│    - High-concurrency batch execution & memory stability               │
│    - Mathematical monotonicity: Area(Weeds) vs Herbicide Savings       │
│    - Ground-truth regression threshold verification                    │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Tier 1: Feature Coverage (Core Happy Path)
Tier 1 ensures that every user-facing capability and core workflow functions correctly on standard inputs:
- **Full Perception-to-Actuation Flow**: Ingests raw input imagery, performs zero-shot detection via Grounding DINO, segments instance masks via SAM 2, executes active error-centroid refinement when confidence falls below threshold, calculates spray coverage and chemical savings, and populates `GraphState` artifacts.
- **Real-World Fixture Testing**: Executes the pipeline on actual agricultural field imagery (`tests/fixtures/sample/cotton_*.jpg` and `tests/fixtures/sample/beet_*.png`) to confirm end-to-end functionality on diverse crop foliage and lighting conditions.
- **Contract Verification of State Dictionaries**: Validates that keys, types, and constraints defined in `PROJECT.md` Interface Contracts (`Box`, `Mask`, `SprayMap`, `Artifact`) are completely satisfied.
- **Safe RAG Diagnosis**: Verifies that known agronomic queries return evidence-grounded prescriptions with mandatory disclaimers and citations, while unknown queries gracefully return `no_knowledge_found` without inventing fictitious recommendations.

### 3.2 Tier 2: Boundary, Robustness & Fault Tolerance
Tier 2 subjects the system to boundary extremes, environmental deficiencies, and malformed inputs:
- **Image Dimension Extremes**: Tests processing of 1x1 single-pixel images, ultra-thin aspect ratios (10x1000 and 1000x20), and completely blank (all-black, all-white) imagery.
- **Corrupt & Missing Inputs**: Tests non-existent file paths, truncated/corrupted image byte buffers, and missing state attributes.
- **Missing Optional Dependencies**: Tests the execution path when optional third-party packages are missing:
  - If `laya` is absent, the system must transparently activate native deterministic reflex triage.
  - If `chromadb` is absent, calls requiring Vector Store must cleanly raise informative `ImportError` or utilize offline hash embeddings.
  - If `cv2` (OpenCV) is absent, morphological dilation must seamlessly fall back to pure-NumPy dilation without crashing.
- **Agronomic Safety Extremes**: Tests 0% weed infestation (yielding 100% chemical savings) and 100% saturated infestation (triggering spray safety suppression, since spot-spraying is agronomically unviable when infestation exceeds 85%).
- **Spray Map Mathematical Invariants**: Enforces strict invariants:
  - Invariant 1: $0.0\% \le \text{infestation\_percentage} \le 100.0\%$
  - Invariant 2: $0.0\% \le \text{chemical\_savings\_percentage} \le 100.0\%$
  - Invariant 3: $\text{Savings}(\text{mask}) \le 1.0 - \frac{\text{area}(\text{mask})}{\text{total\_area}}$
  - Invariant 4: Monotonicity — $\text{Area}_A \subseteq \text{Area}_B \implies \text{Savings}(A) \ge \text{Savings}(B)$

### 3.3 Tier 3: Interface Contracts & Cross-Module Integration
Tier 3 focuses on cross-boundary schemas and provider abstractions:
- Validates the standardized `RouterDecision` schema across deterministic, Laya, and Clef Flash backends.
- Validates the unified `BaseAgronomyProvider` request/response contracts for both local Qwen and hosted Groq backends.
- Validates LangGraph `StateGraph` conditional transitions and cyclic loop limits (max 2 refinement iterations).

### 3.4 Tier 4: Adversarial Verification, Safety Guardrails & Stress
Tier 4 performs adversarial red-teaming:
- Injects banned CIBRC chemicals and excessive chemical dosages to confirm statutory filters reject unapproved prescriptions.
- Verifies absence of hallucinated chemical names on unknown weed species.
- Stress-tests memory retention and execution determinism across large image batches.

---

## 4. Test Harness Architecture (`tests/e2e/`)

### 4.1 Directory Layout
```
tests/e2e/
├── __init__.py                           # Package marker
├── fixtures.py                           # Synthetic & real image generators, mock knowledge stores
├── runner.py                             # Dedicated tiered E2E test runner CLI
├── test_tier1_feature_coverage.py        # Tier 1: End-to-end pipeline, contracts, happy paths
└── test_tier2_boundary_robustness.py     # Tier 2: Corrupt inputs, empty images, dependency fallbacks
```

### 4.2 Fixture Management (`tests/e2e/fixtures.py`)
- `create_test_field_image(width, height, weed_boxes)`: Generates RGB field imagery with synthetic vegetation patches.
- `create_blank_image(width, height, color)`: Generates uniform blank images (black, white, green).
- `create_corrupt_image_bytes()`: Generates malformed byte sequences mimicking damaged file downloads.
- `get_sample_image_path(filename)`: Resolves paths to repository sample images (`tests/fixtures/sample/`).
- `MockKnowledgeStore`: Fast, in-memory reference store implementing `query()` for offline testing of RAG contracts without disk I/O.

### 4.3 Custom Tiered Runner (`tests/e2e/runner.py`)
Provides both human-readable terminal output and structured JSON summaries:
```bash
# Run all E2E tests
python3 tests/e2e/runner.py --all

# Run Tier 1 tests only
python3 tests/e2e/runner.py --tier 1

# Run Tier 2 tests only
python3 tests/e2e/runner.py --tier 2

# Output machine-readable JSON summary for CI/CD
python3 tests/e2e/runner.py --all --json

# Standard unittest discovery compatibility
python3 -m unittest discover tests/e2e -v
```

---

## 5. Contract & Data Model Verification Rubric

Every test assertion rigorously verifies data types, numerical ranges, and semantic contracts:

### 5.1 `Box` Contract
- `x1, y1, x2, y2`: Floats satisfying $0 \le x_1 < x_2 \le W$ and $0 \le y_1 < y_2 \le H$.
- `score`: Float satisfying $0.0 \le \text{score} \le 1.0$.
- `label`: Non-empty string identifying the botanical class.

### 5.2 `Mask` Contract
- `mask_array`: 2D `np.ndarray` of dtype `bool`, shape matching image dimensions $(H, W)$.
- `predicted_iou`: Float satisfying $0.0 \le \text{predicted\_iou} \le 1.0$.
- `box`: Valid `Box` dictionary from which the mask was segmented.

### 5.3 `SprayMap` Contract
- `infestation_percentage`: Float in $[0.0, 100.0]$.
- `chemical_savings_percentage`: Float in $[0.0, 100.0]$.
- `weed_count`: Integer $\ge 0$ equal to the number of segmented masks.
- `buffer_pixels`: Integer $\ge 0$.
- `target_resolution`: Dictionary with integer `"width"` and `"height"`.
- Artifact: Stored under `state["artifacts"]["spray_map"]` with `type == ArtifactType.SPRAY_MAP` and binary composite mask payload.

### 5.4 `PrescriptionReport` Contract
- `status`: Must be `"ok"` (evidence found) or `"no_knowledge_found"` (unknown query).
- `evidence`: Non-empty list of citations if `status == "ok"`, strictly empty list if `status == "no_knowledge_found"`.
- `disclaimer`: Mandatory non-empty regulatory disclaimer string.

---

## 6. Pass/Fail Semantics & Regression Gates

1. **Strict Exit Codes**:
   - Exit code `0`: 100% of discovered tests passed.
   - Exit code `1`: One or more tests failed or encountered errors.
2. **Zero-Tolerance Failure Criteria**:
   - Contract violation (missing mandatory key, incorrect type) -> **HARD FAILURE**.
   - Safety breach (invented herbicide dosage or chemical on empty retrieval) -> **CRITICAL FAILURE**.
   - Out-of-bounds mathematical invariant (negative savings, NaN percentage) -> **HARD FAILURE**.
   - Unhandled exception on corrupt/empty input -> **HARD FAILURE**.
3. **Flakiness Elimination**:
   - All synthetic generators use deterministic seeds and predictable geometry.
   - No sleep/polling loops in tests; all operations execute synchronously.
4. **Escalation Protocol**:
   - When an implementation defect is identified during E2E test authoring, the test writer documents the verbatim failure in `handoff.md` and escalates to the implementing track rather than patching production code directly.
