# Project: AgriAgent Week 2 Master Execution Plan
# From Integrated Prototype to Measured, Reproducible, End-to-End System

## Architecture
AgriAgent is a hybrid edge-and-cloud dual-system robotic agronomy platform:
1. **System 1 (Local Real-Time Reflex, <40ms)**: Edge vision pipeline running Grounding DINO detection, Meta SAM 2 instance segmentation, morphological mask refinement, local deterministic triage routing, and spray map generation.
2. **System 2 (Deliberative Agronomic Intelligence, Asynchronous)**: Ambiguous weed/symptom diagnosis via VLM (Qwen3.5-9B / Groq), evidence-based retrieval over ICAR/CIBRC statutory corpus, and safe chemical prescription generation with dosage limits.
3. **Application & Delivery Layer**: Streamlit interactive dashboard with Mock/Live toggles, GeoJSON field maps, and reproducible Kaggle GPU benchmarking workflow.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Repository Audit & Dossier Reconciliation | Document confirmed facts, 0.99 IoU reality, Laya limitations, and architectural discrepancies | M1 | Survey (Phase A) |
| 2 | Ground-Truth Dataset & Manifests | Versioned evaluation dataset, annotation download, held-out splits for cotton & sugarbeet | M1 | Survey / Section 3 |
| 3 | Independent Vision Evaluation Harness | Compute true ground-truth mask IoU, Dice, Precision, Recall, and mAP using `compute_iou` | M1 | Survey / Section 3 |
| 4 | Geometric Mask Refinement Fix | Replace flawed bounding box subtraction with morphological contour/gradient refinement | M2 | Survey / Section 3 |
| 5 | Full LangGraph StateGraph & Cyclic Loopback | Add cyclic refinement recursion and integrate System-2 node into StateGraph | M2 | Survey / Section 2 |
| 6 | Router Architecture & Clef Flash Comparison | Standardize routing contract; benchmark Deterministic vs Laya vs Cloudflare Clef Flash | M2 | Survey / Section 4 |
| 7 | Table-Aware Ingestion & Rich Metadata | Parse ICAR Bulletin tables into structured chunks with crop, active ingredient, dosage metadata | M3 | Survey / Section 5 |
| 8 | Distance-Gated Retrieval & Safe Fallback | Add similarity distance threshold to `KnowledgeStore.query()` to enable safe `no_knowledge_found` | M3 | Survey / Section 5 |
| 9 | Statutory Safety & Dosage Ceiling Filter | Enforce CIBRC banned chemical filter and dosage rate upper bounds | M3 | Survey / Section 5 |
| 10 | Unified LLM/VLM Provider Interface | Configurable contract (`BaseAgronomyProvider`) supporting local Qwen3.5-9B and hosted Groq | M3 | Survey / Section 6 |
| 11 | Streamlit UI Pipeline Integration | Connect `app/app.py` to `VisionWorkflowRunner` with Mock/Live toggle, dynamic KPIs, error handling | M4 | Survey / Section 10 |
| 12 | Layered GitHub Actions CI/CD | 10-layer quality pipeline (linting, type checks, contracts, unit, security, UI smoke) | M4 | Survey / Section 7 |
| 13 | Build System & Dependency Standardization | Author `pyproject.toml`, add `.env.example`, resolve missing dependencies in `requirements.txt` | M4 | Survey / Section 2 |
| 14 | Reproducible Kaggle GPU Runner & CLI | Author `kernel-metadata.json`, refactor notebook to import `src/`, execute via Kaggle CLI | M5 | Survey / Section 8 |
| 15 | Controlled Vision & Routing Ablations | Execute ablations A-E, record metrics, latency distributions, and chemical savings | M5 | Survey / Section 3 |
| 16 | End-to-End System Integration & Contract Validation | Full pipeline validation from image upload through detection, segmentation, routing, and RAG | M5 | Survey / Section 10 |
| 17 | Comprehensive E2E Test Suite (Tiers 1-4) | Opaque-box requirement-driven test suite with >=11*N tests; publish `TEST_READY.md` | E2E | Section 1, 7 |
| 18 | Release Candidate & Deliverables Verification | Final documentation, setup guides, evaluation report, and Victory Audit readiness | M6 | Section 11 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Audit Synthesis & Vision Ground-Truth Baseline | Dataset manifests, annotations, ground-truth evaluation harness, audit report | None | DONE |
| M2 | Core Vision, Refinement & Router Hardening | Refinement heuristic fix, LangGraph cyclic loop, router benchmark & contracts | M1 | IN_PROGRESS |
| M3 | Agronomy RAG, Safety & Provider Interface | Table ingestion, distance gating, dosage filter, unified Qwen/Groq provider | M1 | IN_PROGRESS |
| M4 | Streamlit Application & CI/CD Quality Pipeline | App pipeline integration, Mock/Live toggle, layered CI/CD, pyproject.toml | M2, M3 | IN_PROGRESS |
| M5 | E2E Integration, Kaggle Runner & Ablation Report | Full pipeline integration, Kaggle CLI execution, ablations A-E report | M4 | PLANNED |
| M6 | Final Milestone: 100% E2E Pass & Release Candidate | Pass 100% E2E test suite (Tiers 1-4), adversarial hardening, release package | M5, E2E | PLANNED |
| E2E| E2E Testing Track | Independent requirement-driven test suite (Tiers 1-4) and `TEST_READY.md` | M1 | IN_PROGRESS |

## Interface Contracts

### 1. Vision Perception Contract (`src/state.py`)
- `Box`: `{x1: float, y1: float, x2: float, y2: float, label: str, score: float}` (normalized [0, 1] or absolute pixel coords documented).
- `Mask`: `{mask_array: np.ndarray (H, W bool), predicted_iou: float, ground_truth_iou: Optional[float], box: Box, label: str}`
- `SprayMap`: `{spray_mask: np.ndarray, infestation_percentage: float, chemical_savings_percentage: float, grid_coordinates: List[Tuple[float, float]]}`

### 2. Triage & Routing Contract (`src/agents/router_contract.py`)
- Inputs: `detection_confidence: float`, `predicted_iou: float`, `area_pixels: int`, `species_ambiguity: bool`, `image_crop: Optional[np.ndarray]`
- Outputs: `RouterDecision`:
  - `action`: `ACCEPT` | `REFINE` | `ESCALATE_SYSTEM2` | `SUPPRESS_SPRAY`
  - `reason`: `str`
  - `latency_ms`: `float`
  - `backend`: `deterministic` | `laya` | `clef_flash`

### 3. Agronomy Provider Contract (`src/agronomy/provider_contract.py`)
- `LLMRequest`: `{system_prompt: str, user_prompt: str, image: Optional[Any], temperature: float, timeout_seconds: float}`
- `LLMResponse`: `{provider: str, model_name: str, text_content: str, parsed_json: Optional[Dict[str, Any]], prompt_tokens: int, completion_tokens: int, latency_ms: float}`

### 4. Chemical Prescription Contract (`src/agronomy/prescription_schema.py`)
- `ChemicalPrescription`:
  - `status`: `"ok"` | `"no_knowledge_found"` | `"unapproved_chemical_flagged"`
  - `crop`: `str`
  - `target_weed`: `str`
  - `active_ingredient`: `Optional[str]`
  - `formulation`: `Optional[str]`
  - `dosage_ai_g_per_ha`: `Optional[float]`
  - `water_volume_l_per_ha`: `Optional[float]`
  - `pre_harvest_interval_days`: `Optional[int]`
  - `toxicity_band`: `Optional[str]` (RED | YELLOW | BLUE | GREEN)
  - `citations`: `List[CitationRecord]` where `CitationRecord` has `{source: str, page: int, authority: str, text_snippet: str}`
  - `disclaimer`: `str`

## Code Layout
- `src/`
  - `state.py`: Central Pydantic/TypedDict state contracts
  - `workflow.py`: `VisionWorkflowRunner` and LangGraph StateGraph
  - `vision/`
    - `grounding_dino.py`: Grounding DINO detection engine + fallbacks
    - `sam2_wrapper.py`: Meta SAM 2 segmenter + fallbacks
    - `refinement.py`: Morphological mask refinement algorithms
    - `visualization.py`: Overlay and annotation rendering
  - `agents/`
    - `router_contract.py`: Standardized routing interface
    - `laya_router.py`: Laya router wrapper
    - `deterministic_router.py`: Fast reflex threshold router
    - `clef_flash_router.py`: Cloudflare Clef Flash adapter
  - `agronomy/`
    - `knowledge_store.py`: Table-aware ingestion, ChromaDB vector store, distance gating
    - `prescription.py`: Structured chemical prescription and dosage filter
    - `provider_contract.py`: Shared LLM provider interface
    - `providers/`: `local_qwen.py`, `hosted_groq.py`
    - `system2_node.py`: Asynchronous deliberative reasoning node
    - `vlm_critic.py`: Visual diagnosis using verified model weights
  - `evaluation/`
    - `iou_dice.py`: Ground-truth IoU and Dice computation
    - `benchmark_runner.py`: Dataset evaluation harness
- `app/`
  - `app.py`: Streamlit application
- `tests/`
  - `unit/`: Component math, geometry, and parser tests
  - `contract/`: State schema and provider contract tests
  - `integration/`: Complete workflow tests with deterministic fakes
  - `safety/`: Dosage ceilings and banned chemical tests
  - `e2e/`: Requirement-driven end-to-end tests (Tiers 1-4)
- `data/`
  - `knowledge_base/`: ICAR / CIBRC statutory PDFs
  - `manifests/`: Ground-truth dataset manifests and split definitions
- `notebooks/`
  - `agriAgentShared.ipynb`: Kaggle GPU experiment notebook
  - `kernel-metadata.json`: Kaggle CLI configuration metadata
