# Phase A Repository Audit Report: AgriAgent Architecture, Discrepancies, and Quality Baseline

**Document Version:** 1.0.0 (Phase A Final Audit Synthesis)  
**Date:** 2026-10-11  
**Project:** AgriAgent — Hybrid Edge-and-Cloud Autonomous Agronomy System  
**Repository:** https://github.com/Chaitanya-666/agriAgent  
**Authors:** Teamwork Preview Audit Engineering Group (Synthesis of Explorer Surveys 1, 2, 3)  
**Target Milestone:** Milestone 1 (Audit Synthesis & Vision Ground-Truth Baseline)

---

## 1. Executive Summary & Audit Mandate

In accordance with the Week 2 Master Execution Plan (`ORIGINAL_REQUEST.md`), a forensic technical audit of the AgriAgent repository was executed across the main branch codebase, commit history, dependencies, test suites, datasets, notebooks, and technical documentation. The primary objective of Phase A is to separate verified executable capabilities from aspirational claims made in the Week 1 Technical Dossier, establish a factual baseline, and formulate rigorous acceptance criteria.

The audit revealed that while AgriAgent possesses a modular, well-architected dual-system skeleton with robust mock fallbacks, significant discrepancies exist between the documented performance claims and the executable codebase:
1. **The "0.99 IoU" Truth:** The reported 0.99 IoU on field imagery was Meta SAM 2's internal predicted mask quality estimate (`iou_predictions`), not an independently calculated overlap with ground-truth masks. No ground-truth annotations existed in the repository, and `src/evaluation/iou_dice.py` was never invoked in the inference pipeline.
2. **Laya Router Reality:** The installed `laya` package is a text-only classification engine. Its current integration serializes numerical floats into English strings to evaluate inequalities (`predicted_iou < threshold`), while 100% of safety-critical decisions bypass Laya via hardcoded Python rules.
3. **Refinement Heuristic Flaw:** The error centroid calculation in `src/vision/refinement.py` subtracts the organic plant mask from a solid rectangular bounding box. Because plant foliage is non-rectangular, background soil in the box corners dominates the difference, erroneously prompting SAM 2 with background points labeled as positive.
4. **Agronomy RAG Subsystem Gaps:** `KnowledgeStore` uses naive character slicing without table awareness, collapsing statutory tabular data; queries lack a distance threshold, making `no_knowledge_found` unreachable; and `vlm_critic.py` targets a non-existent Hugging Face repository (`Qwen/Qwen3-VL-2B-Instruct`).
5. **Streamlit UI Disconnect:** `app/app.py` is a detached mock demonstrator running hardcoded bounding boxes, static KPIs, and hardcoded college campus GeoJSON coordinates rather than calling the `VisionWorkflowRunner`.
6. **Dataset & CI Gaps:** `data/download_datasets.sh` discarded annotation JSONs while downloading images; target fixture directories were missing; and CI tests ran solely in mock mode across minimal dependencies.

---

## 2. Component-by-Component Confirmed Facts & Technical Audit

### 2.1 System 1 Vision Pipeline (`src/vision/`)

#### 2.1.1 Grounding DINO Object Detection (`grounding_dino.py`)
- **Engine Architecture:** Wraps `IDEA-Research/grounding-dino-tiny` using Hugging Face `transformers` (`AutoProcessor`, `AutoModelForZeroShotObjectDetection`).
- **Prompt Formatting:** Enforces mandatory trailing period syntax (`formatted_prompt += " ."`) in accordance with Grounding DINO text encoder requirements.
- **Mock Fallback:** When `torch` or `transformers` is missing or fails to initialize on CPU, automatically sets `mock_mode = True` and synthesizes 3 deterministic boxes:
  - Box 1: `(0.18, 0.22, 0.38, 0.44)` conf: 0.91
  - Box 2: `(0.55, 0.30, 0.78, 0.58)` conf: 0.86
  - Box 3: `(0.32, 0.62, 0.52, 0.85)` conf: 0.79
- **Coordinate Normalization:** Live predictions produce unnormalized pixel coordinates `[x1, y1, x2, y2]`. Mock predictions return normalized float coordinates `[0.0, 1.0]`, creating a minor coordinate space discrepancy when client modules do not standardize box representations.

#### 2.1.2 Meta SAM 2 Instance Segmentation (`sam2_wrapper.py`)
- **Backend Implementations:** Supports dual backends: official Meta SAM 2 (`SAM2ImagePredictor`) and Hugging Face `transformers` (`Sam2Model`, `Sam2Processor`).
- **Predicted IoU Extraction:**
  - Meta SAM 2: Extracts `best_score = float(scores[0])` from `predict()`.
  - Hugging Face: Extracts `float(outputs.iou_predictions[0, 0].cpu().item())`.
- **Mock Mask Synthesis:** In mock mode, synthesizes organic leaf contours via coordinate ellipses perturbed with trigonometric noise (`np.sin(xx * 0.35) * np.cos(yy * 0.35) * 0.22`), returning a mock confidence score `predicted_iou = 0.88`.

#### 2.1.3 The 0.99 IoU Dissection & Forensic Evidence
- **Documented Claims:**
  - `README.md` lines 102 & 108: `Predicted IoU: **0.99**`
  - `README.md` line 117: `| **Predicted Mask IoU** | 0.88 (simulated) | **0.99** (SAM 2 inference) | **VERIFIED** |`
  - `docs/AgriAgent_Week1_Master_Technical_Dossier.typ` line 248: `Achieved *IoU: 0.99* and *97.4% chemical savings* on real field imagery.`
- **Codebase Truth:**
  - `src/evaluation/iou_dice.py` contains mathematical implementations of `compute_iou` and `compute_dice` against ground-truth arrays.
  - A global search across `src/`, `scripts/`, and `notebooks/` confirms `compute_iou` is **never imported or executed** in the inference pipeline or notebook experiments.
  - No ground-truth annotations existed in the repository prior to Phase A.
  - In SAM 2, `scores` is an internal self-assessment metric output by an MLP head in the mask decoder predicting the expected quality of the predicted mask.
  - Presenting SAM 2's self-assessed confidence as independent ground-truth IoU conflates model confidence with empirical accuracy. Because `predicted_iou = 0.99 >= 0.85`, the refinement loop was bypassed entirely in Week 1 live runs.

#### 2.1.4 Geometric Mask Refinement Flaw (`refinement.py`)
- **Algorithm Analysis:**
  `compute_error_centroid(mask: np.ndarray, box: Tuple[int, int, int, int])` creates a solid binary rectangle `box_mask[y1:y2, x1:x2] = True` and computes:
  ```python
  under_seg = box_mask & ~mask   # Box region not covered by mask
  over_seg = mask & ~box_mask    # Mask region outside box
  ```
- **The Defect:** Agricultural plants are organic non-convex geometries. A tight bounding box around a plant necessarily contains large regions of inter-row soil, shadows, and crop residue in the corners.
- Consequently, `under_seg` is dominated by non-plant background pixels, while `over_seg` is virtually zero because SAM 2 was prompted within the bounding box.
- Therefore, `under_seg.sum() > over_seg.sum()` evaluates to `True` virtually 100% of the time, and the computed centroid `(xs.mean(), ys.mean())` lands directly on background soil. Passing this point with `is_positive = True` instructs SAM 2 to expand the mask into soil, corrupting segmentation precision.

---

### 2.2 Routing & Arbitration Architecture (`src/agents/laya_router.py`)

#### 2.2.1 Package Nature & Multimodal Infeasibility
- The installed `laya` package (ConvAI Innovations, PyPI) is an NLP decision library. It consumes text strings and question queries and outputs classified text labels and calibrated probabilities.
- It possesses zero computer vision capabilities: no support for image arrays, tensors, visual embeddings, or bounding coordinates.

#### 2.2.2 Current Stringified Integration
- In `evaluate_mask_refinement`:
  ```python
  state = f"Target: {label}, Predicted IoU: {predicted_iou:.3f}, Mask Area: {area_pixels} px, Quality Threshold: {threshold}"
  questions = ["Does this segmentation mask fail the quality threshold and require geometric point refinement?"]
  ```
  An external NLP model is invoked to evaluate a simple floating-point numerical comparison (`predicted_iou < threshold`), incurring 5–40 ms latency and network/process failure risk.
- In `evaluate_system2_escalation`:
  All high-confidence detections (`conf >= 0.70 and iou >= 0.80`) are resolved by a deterministic Python guard without querying Laya.
- In `verify_spray_safety`:
  100% deterministic rule (`infestation_pct <= 85.0%`).

#### 2.2.3 Router Assessment
- Laya provides no visual discernment for System-1 fast reflexes.
- Autonomous field spraying at 10–20 km/h requires deterministic execution in <40 ms. Local threshold routing is instantaneous (<0.001 ms), completely offline, zero-cost, and non-hallucinatory.
- Cloudflare Clef Flash (a 9B multimodal decision model) should be evaluated for System-2 deliberative triage where image crops of ambiguous foliage can be visually inspected, but must not gate System-1 real-time nozzle actuation.

---

### 2.3 State, Workflow, and Orchestration (`src/state.py`, `src/workflow.py`)

- **State Schemas (`src/state.py`):**
  Defines `Box`, `Mask`, `Artifact`, `ArtifactType`, and `GraphState`. `GraphState` contains declared fields `ground_truth_masks` and `evaluation_metrics`, but these fields were unpopulated during pipeline execution.
- **Workflow Coordination (`src/workflow.py`):**
  - `VisionWorkflowRunner`: A native sequential runner coordinating `detect`, `segment`, `refine`, and `spray_map`. Correctly loops refinement up to `max_refinements`.
  - `create_langgraph_workflow()`:
    - Compiles a LangGraph `StateGraph`.
    - Edge from `segment` conditionally branches to `refine` or `spray_map`.
    - Edge from `refine` connects unconditionally to `spray_map`: `builder.add_edge("refine", "spray_map")`.
    - **Discrepancy:** The LangGraph definition lacks a cyclic loopback from `refine` back to the evaluation condition. Refinement can execute at most once in the LangGraph graph.
    - **Discrepancy:** System-2 reasoning is omitted from the LangGraph graph entirely (`spray_map -> END`).

---

### 2.4 Agronomy RAG Subsystem & ICAR/CIBRC Corpus (`src/agronomy/`)

#### 2.4.1 Knowledge Corpus Inspection
- Single document present: `data/knowledge_base/icar_dwr_herbicide_use_bulletin22.pdf.pdf` (note double `.pdf.pdf` extension).
- Document: ICAR - Directorate of Weed Research Bulletin No. 22 (2016), 121 pages.
- Table Coverage: Covers approved herbicide recommendations for Wheat, Rice, Cotton, Maize, Soybean, Sugarcane, Tea, and general horticulture crops.
- **Critical Omission:** Sugar beet (*Beta vulgaris* subsp. *vulgaris*) is completely absent from ICAR recommendations (only table beet / beetroot is briefly noted in Table 4.8). There is zero ICAR statutory herbicide guidance for sugar beet weed control.

#### 2.4.2 Ingestion & Retrieval Deficiencies (`knowledge_store.py`)
- **Naive Chunking:** `_chunks(text, size=900, overlap=150)` collapses all whitespace with `\s+` and takes fixed character slices. This destroys table column alignments, severing herbicide active ingredients from approved crops, application dosages, and pre-harvest intervals.
- **Sparse Metadata:** Stores only `source`, `page`, and `authority` (derived from filename substring `"cib"` or `"icar"`). Does not index crop, target weed, chemical name, or toxicity class.
- **Unbounded Retrieval:** `KnowledgeStore.query()` queries ChromaDB and returns top $k$ chunks without filtering on cosine/L2 distance.
- **Unreachable Safe Fallback:** In `prescription.py`, `status = "ok" if hits else "no_knowledge_found"`. Because `hits` is non-empty for any query whenever documents exist in ChromaDB, the system returns `"ok"` with irrelevant evidence for unsupported crops or nonsensical weed queries.

#### 2.4.3 VLM Model Identifier & Fragile Parser (`vlm_critic.py`)
- Sets `DEFAULT_MODEL = "Qwen/Qwen3-VL-2B-Instruct"`. This Hugging Face repository does not exist (official repo is `Qwen/Qwen2-VL-2B-Instruct` or `Qwen/Qwen2.5-VL-3B-Instruct`), causing 404 errors if initialized with live weights.
- Regex parser `re.search(r"\{.*\}", text, re.S)` greedily matches across markdown blocks, failing on explanations containing brace characters.

#### 2.4.4 LLM Factory (`src/llm_factory.py`)
- Orphaned prototype using `sys.argv` inspection (`"--local" in sys.argv`) and hardcoded localhost IP `http://127.0.0.1:8888/v1`.
- Imports `langchain_groq` and `langchain_openai`, which were undeclared in `requirements.txt`.

---

### 2.5 Streamlit Application (`app/app.py`)

- **Prototype Disconnect:** `app/app.py` is an isolated UI demonstration that does not instantiate `VisionWorkflowRunner`, `GroundingDINOEngine`, or `SAM2Segmenter`.
- **Hardcoded Presets:** Detections are hardcoded to preset box coordinates; KPIs are hardcoded strings (`"18.2%"` weed area, `"74.6%"` chemical reduction); and the prescription map displays static GeoJSON polygons centered on the VJTI Mumbai college campus (`[72.8550, 19.0220]`).
- **Missing Live Mode:** The UI lacks any toggle or execution pathway to run live model inference on uploaded images.

---

### 2.6 Datasets, Annotations, and Test Infrastructure

#### 2.6.1 Downloader Script Defect (`data/download_datasets.sh`)
- Targeted Kaggle datasets `yuzhenlu/cottonweeddet3` and `wangyongkun/sugarbeetsandweeds`.
- Parsed annotation file paths via `grep 'annotations/.*\.json$'`, extracted basename `$n`, but only downloaded `CottonWeedDet3/images/$n.$ext`, completely discarding the annotation JSON files.
- The target directories `tests/fixtures/cotton/` and `tests/fixtures/sugarbeet/` did not exist in the repository.

#### 2.6.2 Existing Imagery (`tests/fixtures/sample/`)
- Contains 20 unannotated field images:
  - 10 Sugar Beet images: `beet_X-10-0.png` through `beet_X-170-1.png` ($640 \times 640$ PNG).
  - 10 Cotton images: `cotton_20190613_6062W_CM_11.jpg` through `cotton_20190613_6062W_CM_40.jpg` ($640 \times 480$ JPEG).
- Prior to Phase A, zero ground-truth bounding boxes, segmentation masks, or class labels existed for these images.

#### 2.6.3 CI/CD & Kaggle GPU Pipeline
- `.github/workflows/ci.yml` installed minimal ad-hoc dependencies (`pip install numpy pillow pyyaml pydantic chromadb`), skipping all deep learning frameworks.
- The test suite of 24 tests passed in <0.05 seconds purely via synthetic mock math.
- Kaggle notebook `notebooks/agriAgentShared.ipynb` lacked `kernel-metadata.json`, preventing automated headless execution via the Kaggle CLI.

---

## 3. Comprehensive Architectural Risk Matrix

| Risk ID | Subsystem | Description | Impact | Likelihood | Mitigation Strategy |
|:---|:---|:---|:---:|:---:|:---|
| **RSK-01** | Evaluation | Conflating SAM 2 internal confidence with ground-truth accuracy undermines academic credibility | High | Confirmed | Establish human-verified ground-truth annotations and report empirical `compute_iou` / `compute_dice`. |
| **RSK-02** | Vision | Refinement heuristic selects background soil pixels as positive prompt, degrading mask precision | High | Confirmed | Replace bounding box subtraction with morphological boundary erosion/dilation and edge difference analysis. |
| **RSK-03** | Agents | Laya router introduces unnecessary latency and failure modes into System-1 real-time spray reflexes | Medium | Confirmed | Enforce local deterministic threshold routing for System 1; restrict learned LLM/VLM models to System 2. |
| **RSK-04** | Agronomy | Naive character chunking splits tabular dosage data, generating inaccurate or hallucinated chemical advice | High | Confirmed | Ingest ICAR bulletin tables into structured markdown/JSON with explicit column semantics (crop, dose, PHI). |
| **RSK-05** | Agronomy | Lack of distance gating in RAG vector query prevents safe `no_knowledge_found` fallback | High | Confirmed | Add cosine distance threshold cutoff to `KnowledgeStore.query()` and test empty retrieval behavior. |
| **RSK-06** | Agronomy | Non-existent Hugging Face model identifier `Qwen/Qwen3-VL-2B-Instruct` crashes live System-2 initialization | Medium | Confirmed | Standardize model identifiers to valid releases (`Qwen/Qwen2.5-VL-3B-Instruct` or Groq hosted API). |
| **RSK-07** | UI / App | Streamlit application disconnect leaves user experience disconnected from core pipeline | Medium | Confirmed | Refactor `app/app.py` to invoke `VisionWorkflowRunner` directly with dynamic metric display. |
| **RSK-08** | Workflows | LangGraph StateGraph omits cyclic refinement loop and System-2 reasoning node | Medium | Confirmed | Add cyclic conditional edge in LangGraph and incorporate deliberative System-2 node. |
| **RSK-09** | CI/CD | CI passes on mock fallbacks without catching packaging or dependency regressions | Medium | Confirmed | Implement layered 10-tier CI pipeline with contract tests, linting, and GPU benchmark automation. |

---

## 4. Phase Remediation Plan & Acceptance Criteria

### Milestone 1: Audit Synthesis & Vision Ground-Truth Baseline (Current)
- [x] Author comprehensive Phase A Audit Report (`docs/audit_report_phase_a.md`).
- [x] Fix dataset downloader (`data/download_datasets.sh`) to download annotation JSONs and create directories.
- [x] Create ground-truth annotations (`tests/fixtures/annotations/sample_ground_truth.json`) for all 20 sample images with verified boxes, labels, and polygons.
- [x] Author versioned evaluation split manifest (`data/manifests/eval_manifest_v1.json`).
- [x] Implement independent benchmark harness (`src/evaluation/benchmark_runner.py`) computing mIoU, mDice, precision, recall, F1, latency, and chemical savings.
- [x] Author comprehensive unit tests in `tests/test_benchmark_runner.py` and verify all tests pass.

### Milestone 2: Core Vision, Refinement & Router Hardening
- Implement morphological contour refinement replacing rectangular box subtraction in `src/vision/refinement.py`.
- Complete cyclic recursion and System-2 node integration in LangGraph `StateGraph`.
- Establish standardized routing contract (`src/agents/router_contract.py`) and benchmark Deterministic vs Laya vs Cloudflare Clef Flash.

### Milestone 3: Agronomy RAG, Safety & Provider Interface
- Implement table-aware parser for ICAR Bulletin 22 tables.
- Add distance cutoff gating to `KnowledgeStore.query()` enabling safe `no_knowledge_found`.
- Implement statutory dosage ceilings and banned pesticide filters.
- Establish unified `BaseAgronomyProvider` supporting local Qwen and hosted Groq.

### Milestone 4: Streamlit Application & Layered CI/CD
- Refactor `app/app.py` to run `VisionWorkflowRunner` with Mock/Live toggles.
- Standardize build configuration in `pyproject.toml` and provide `.env.example`.
- Build layered GitHub Actions CI/CD pipeline.

### Milestone 5: E2E Integration, Kaggle GPU Runner & Ablation Report
- Configure `kernel-metadata.json` and Kaggle CLI workflow.
- Execute ablations A through E across the evaluation dataset.
- Publish final empirical benchmark results and chemical savings analysis.

---

## 5. Conclusion

Phase A technical investigation confirms that AgriAgent possesses strong foundational abstractions, modular code organization, and comprehensive mock fallbacks. However, critical corrections are necessary: the 0.99 IoU claim must be redefined as SAM 2's predicted confidence, the refinement heuristic must be replaced with genuine morphological logic, Laya must be scoped appropriately, and the agronomy RAG pipeline must be hardened with structured table ingestion and distance gating.

Milestone 1 establishes the verified ground-truth dataset, versioned manifest, and independent benchmark runner required to turn AgriAgent into a scientifically defensible, empirical agricultural AI system.
