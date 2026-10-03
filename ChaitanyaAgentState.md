# AgriAgent: Chaitanya Shinde Project State (`ChaitanyaAgentState.md`)

> **Lead Architect & Author:** Chaitanya Shinde  
> **Project:** AgriAgent — Hybrid Edge Foundation Model Framework for Autonomous Precision Agriculture  
> **Institution:** Veermata Jijabai Technological Institute (VJTI), Mumbai  
> **Current Sprint:** Week 1 Execution Sprint (October 01 – October 07, 2026)  
> **Active Branch:** `chaitanya/foundation-vision`  
> **Remote Origin:** `git@github.com:Chaitanya-666/agriAgent.git`

---

## 1. High-Level Engineering Goals

1. **Dual-Brain Cognitive Split:**
   - **System-1 (Fast Reflex Loop $<40\text{ ms}$):** Zero-shot bounding box perception (Grounding DINO), surgical leaf instance segmentation (Meta SAM 2), closed-loop error-centroid refinement heuristic ($IoU < 0.85$), and downstream precision spray maps.
   - **System-2 (Deliberative Agronomy Reasoning $>1.5\text{ s}$):** Multimodal visual critic (**Qwen3-VL** / **InternVL 3.5**) + ICAR/CIBRC vector knowledge store (ChromaDB + Groq Llama-3.3-70B) for active ingredient prescription and safety warnings.
2. **100% Zero-Lab Dependency Guarantee:**
   - Resilient architectural decouple: every vision module supports dual execution (`mock_mode=True` for instant laptop development, `mock_mode=False` for GPU inference).
   - Zero dependence on erratic college lab hardware.
3. **Strict Git Collaboration & PR Merging:**
   - Feature branches per track: `chaitanya/foundation-vision`, `sumant/vlm-agronomy`, `sahil/cotton-datasets`, `amit/streamlit-ui`.
   - Sunday 6:00 PM IST Code Freeze $\rightarrow$ Sunday 8:00 PM IST Chaitanya PR Merge Review $\rightarrow$ Monday Morning `main` Pull.
4. **Viva Voce & Technical Placement Asset:**
   - Designed to serve as Chaitanya's strongest capstone project in tier-1 company interviews (Google, Microsoft, Kelp, top AI startups) and the final B.Tech VJTI examination under Prof. V. D. Dhore.

---

## 2. Track Progress Board (Week 1)

### 🌿 Track 1: Core AI & Vision Systems
**Owner:** Chaitanya Shinde (`chaitanya/foundation-vision`) — **STATUS: 100% COMPLETED FOR WEEK 1**
- [x] Prune 1,215 lines of legacy SmartDesk workplace agents (`src/agents/smartdesk_agents/`).
- [x] Specialize `src/state.py` into strongly-typed AgriAgent `GraphState`, `Box`, `Mask`, and `Artifact`.
- [x] Implement `src/vision/grounding_dino.py` with Swin-BERT cross-attention and deterministic mock mode.
- [x] Implement `src/vision/sam2_wrapper.py` with Meta SAM 2 promptable masks and active point refinement.
- [x] Refactor `src/evaluation/iou_dice.py` with pure NumPy morphological dilation fallback.
- [x] Build `src/workflow.py` with pure-Python `VisionWorkflowRunner` DAG and LangGraph `create_langgraph_workflow()`.
- [x] Build automated test suite in `tests/test_vision_pipeline.py` (**7/7 tests passing in 0.013s**).
- [x] Provide turnkey Live GPU verification script (`scripts/run_live_pipeline.py`) and Colab notebook (`notebooks/00_colab_live_gpu_verification.ipynb`).
- [x] Author comprehensive 9-page publication-grade technical dossier and viva guide (`docs/AgriAgent_Week1_Technical_Dossier.pdf`).
- [x] Maintain living context in `docs/Week1Context.md` and `TODO.md`.

### 🌾 Track 2: Multimodal VLM & Agronomy Intelligence
**Owner:** Sumant Vetal (`sumant/vlm-agronomy`) — **STATUS: IN PROGRESS**
- [ ] Evaluate **Qwen3-VL-2B/4B** or **InternVL3.5-4B** for fine-grained leaf pathology reasoning in `notebooks/01_vlm_reasoning_experiment.ipynb`. *(Updated: Deprecated legacy Qwen2.5-VL)*.
- [ ] Ingest ICAR & CIBRC weed management recommendations into ChromaDB (`src/agronomy/knowledge_store.py`).
- [ ] Implement agronomy recommendation tool `get_herbicide_prescription(weed_name, crop_stage)`.

### 📊 Track 3: Data Science & Empirical Benchmarking
**Owner:** Sahil Chavan (`sahil/cotton-datasets`) — **STATUS: IN PROGRESS**
- [ ] Build automated dataset downloader script (`data/download_datasets.sh`) for Indian CottonWeeds and SugarBeets.
- [ ] Stage 20 curated test sample images with ground-truth masks in `tests/fixtures/`.
- [ ] Implement metric test suite (`tests/test_metrics.py`) verifying IoU, Dice, and chemical savings calculation.

### 🗺️ Track 4: Geospatial Systems & Full-Stack Deployment
**Owner:** Amit Ingle (`amit/streamlit-ui`) — **STATUS: IN PROGRESS**
- [ ] Build OpenCV mask overlay compositor in `src/vision/visualization.py` (Green = Crop, Red = Weed).
- [ ] Construct responsive dual-panel Streamlit dashboard in `app/app.py`:
  - Upload widget, confidence slider, spray buffer slider.
  - Side-by-side comparison: Raw Field Photo vs. Precision Spray Map.
  - KPI Cards: Weed infestation % and Chemical savings %.
- [ ] Local launch verification (`streamlit run app/app.py`).

---

## 3. Session Log: October 3, 2026 (Saturday Night Sprint)

### Key Architectural Decisions Made:
1. **Complete Pruning of SmartDesk:**
   - Deleted `src/agents/smartdesk_agents/` to eliminate dead code confusion.
   - Refactored `src/state.py` from generic chat state into agricultural domain models (`Box`, `Mask`, `GraphState`).
2. **Resilience Engineering (Zero-Dependency Decoupling):**
   - Wrapped `langchain_core.messages.AnyMessage` with `try/except` in `src/state.py`.
   - Engineered pure NumPy morphological dilation in `src/evaluation/iou_dice.py` so buffer safety margins ($10\text{ cm}$) compute accurately even if `opencv-cv2` is missing.
   - Built dual-mode mock architecture for Grounding DINO and SAM 2 so UI and Data teammates can develop locally without downloading 2+ GB GPU weights.
3. **SOTA VLM Upgrade (Deprecating Qwen2.5-VL):**
   - Upgraded Track 2 target to modern late-2026 SOTA: **Qwen3-VL (2B/4B)** and **InternVL 3.5**.
   - Solves the token explosion problem via Interleaved-MRoPE and fits comfortably in $<3\text{ GB}$ VRAM.

### Testing & Verification Record:
Ran automated test suite: `python3 -m unittest discover tests -v` (and `PYTHONPATH=. python3 -m unittest tests/test_vision_pipeline.py -v`)
* `test_detect_to_state_boxes` $\rightarrow$ **PASS**
* `test_mock_detection_generates_boxes` $\rightarrow$ **PASS**
* `test_compute_error_centroid_under_segmentation` $\rightarrow$ **PASS**
* `test_should_refine` $\rightarrow$ **PASS**
* `test_point_refinement_improves_iou` $\rightarrow$ **PASS**
* `test_segment_boxes_generates_masks` $\rightarrow$ **PASS**
* `test_end_to_end_execution` $\rightarrow$ **PASS**
* **Result:** **7/7 tests passed in 0.014s**.

### Kaggle GPU Execution Diagnosis & Fixes (Oct 3, 2026):
1. **Grounding DINO Argument Deprecation (`transformers >= 4.55.0`):**
   - *Issue:* `post_process_grounded_object_detection()` threw `TypeError: got an unexpected keyword argument 'box_threshold'. Did you mean 'text_threshold'?`
   - *Fix:* Added dual-version fallback in `src/vision/grounding_dino.py` trying `box_threshold` and falling back to `threshold`.
2. **Meta SAM 2 Hydra Config Resolution:**
   - *Issue:* `build_sam2("facebook/sam2-hiera-tiny")` threw `Cannot find primary config 'facebook/sam2-hiera-tiny'`.
   - *Fix:* Switched to official `SAM2ImagePredictor.from_pretrained(self.model_id, device=self.device)` in `src/vision/sam2_wrapper.py`.
3. **Python Package Discovery on Remote Environments:**
   - *Issue:* `unittest` could not resolve `tests.test_vision_pipeline` without package markers.
   - *Fix:* Created `__init__.py` in `src/`, `src/vision/`, `src/agents/`, `src/evaluation/`, and `tests/`, and configured notebooks to use `!PYTHONPATH=. python -m unittest discover tests -v`.

---

## 4. Next Sunday Milestones (October 4, 2026)

1. **Monitor Teammate Branches:** Watch for `amit/streamlit-ui`, `sahil/cotton-datasets`, and `sumant/vlm-agronomy`.
2. **Sunday 6:00 PM Code Freeze:** Ensure all 3 teammates open Pull Requests targeting `main`.
3. **Sunday 8:00 PM PR Integration:** Chaitanya reviews PR diffs, executes test suite, and merges clean PRs into `main`.
4. **Tuesday Demo Dry-Run:** Conduct full local dry-run with Streamlit UI for Prof. V. D. Dhore.
