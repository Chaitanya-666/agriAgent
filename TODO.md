# AgriAgent: Engineering Sprint Progress & Task Board

> **Project:** AgriAgent — Hybrid Edge Foundation Model Framework for Autonomous Precision Agriculture  
> **Institution:** Veermata Jijabai Technological Institute (VJTI), Mumbai  
> **Lead & Architect:** Chaitanya Shinde  
> **Branch Strategy:** Feature branches per track $\rightarrow$ Sunday 6 PM PR $\rightarrow$ Sunday 8 PM Merge to `main`.

---

## 📅 Week 1 Execution Sprint (Oct 01 – Oct 07, 2026)

**Weekly Target:** Working end-to-end prototype slice for Prof. V. D. Dhore (Tuesday Oct 6/7 demo). Zero blocking dependencies.

### 🌿 Track 1: Core AI & Vision Systems
**Owner:** Chaitanya Shinde (`chaitanya/foundation-vision`)
- [x] **Task 1.0:** Prune SmartDesk legacy agents (`workspace_agent`, `productivity_agent`, `knowledge_agent`) and specialize `src/state.py`.
- [x] **Task 1.1:** Build `src/vision/grounding_dino.py`:
  - [x] Zero-shot open-vocabulary bounding box detector interface.
  - [x] Hugging Face / IDEA-Research model loader (`IDEA-Research/grounding-dino-tiny`).
  - [x] Deterministic mock fallback mode (`mock_mode=True`) for lightweight CPU/laptop testing.
  - [x] Standalone test & verification script.
- [x] **Task 1.2:** Build `src/vision/sam2_wrapper.py`:
  - [x] Meta AI SAM 2 promptable mask generator wrapper.
  - [x] Bounding-box-to-mask conversion (`predict_masks(image, boxes)`).
  - [x] Deterministic mock fallback mode for fast local verification.
- [x] **Task 1.3:** Connect `src/vision/refinement.py` closed-loop logic:
  - [x] Active IoU threshold evaluation ($\text{IoU} < 0.85$).
  - [x] Error centroid calculation for point prompt correction.
- [x] **Task 1.4:** Build `src/workflow.py` LangGraph state graph linking System-1 vision reflex nodes.
- [x] **Task 1.5:** Create end-to-end test verification in `tests/test_vision_pipeline.py` (7/7 unit tests passing).
- [x] **Task 1.6:** Provide turnkey Live GPU verification script (`scripts/run_live_pipeline.py`) and unified GPU notebook (`notebooks/agriAgentShared.ipynb`).
- [x] **Task 1.7:** Author comprehensive 9-page technical dossier & viva defense guide (`docs/AgriAgent_Week1_Technical_Dossier.pdf`).
- [x] **Task 1.8:** Kaggle & Colab GPU verification hardening:
  - [x] Patch Grounding DINO dynamic `box_threshold` / `threshold` argument handling (`transformers >= 4.55.0`).
  - [x] Integrate official `SAM2ImagePredictor.from_pretrained` loader (eliminates Hydra config error).
  - [x] Add package `__init__.py` markers across `src/`, `src/vision/`, `src/agents/`, `src/evaluation/`, `tests/`.
  - [x] Consolidate one-click Kaggle & Colab verification notebook (`notebooks/agriAgentShared.ipynb`).

---

### 🌾 Track 2: Multimodal VLM & Agronomy Intelligence
**Owner:** Sumant Vetal (`sumant/vlm-agronomy`)
- [ ] **Task 2.1:** Evaluate Qwen3-VL (2B/4B) or InternVL 3.5 (2B/4B) for visual reasoning on field photos (`notebooks/01_vlm_reasoning_experiment.ipynb`).
- [ ] **Task 2.2:** Ingest ICAR & CIBRC weed management recommendations into ChromaDB (`src/agronomy/knowledge_store.py`).
- [ ] **Task 2.3:** Implement agronomy recommendation tool `get_herbicide_prescription(weed_name, crop_stage)`.

---

### 📊 Track 3: Data Science & Empirical Benchmarking
**Owner:** Sahil Chavan (`sahil/cotton-datasets`)
- [ ] **Task 3.1:** Create automated dataset downloader script (`data/download_datasets.sh`) for Indian CottonWeeds and SugarBeets.
- [ ] **Task 3.2:** Stage 20 curated test sample images with ground-truth masks in `tests/fixtures/`.
- [ ] **Task 3.3:** Implement standalone metric test suite (`tests/test_metrics.py`) verifying IoU, Dice, and chemical savings calculation.

---

### 🗺️ Track 4: Geospatial Systems & Full-Stack Deployment
**Owner:** Amit Ingle (`amit/streamlit-ui`)
- [ ] **Task 4.1:** Build OpenCV mask overlay compositor in `src/vision/visualization.py` (Green = Crop, Red = Weed).
- [ ] **Task 4.2:** Construct responsive dual-panel Streamlit dashboard in `app/app.py`:
  - [ ] Sidebar controls (image upload, confidence slider, spray buffer distance).
  - [ ] Dual columns: Original Field Photo vs. Precision Spray Map.
  - [ ] Dynamic KPI metrics cards (Weed % and Chemical Savings %).
- [ ] **Task 4.3:** Verify live interactive local launch: `streamlit run app/app.py`.

---

## 🏆 Viva & Technical Placement Milestones
- [ ] **Milestone 1 (Week 1):** Zero-Shot Grounded-SAM 2 prototype executing on sample cotton field image with mock + real support.
- [ ] **Milestone 2 (Week 2):** Dual-Brain LangGraph coordination (Fast vision reflex $<40\text{ ms}$ + Slow VLM RAG reasoning).
- [ ] **Milestone 3 (Week 3):** Full-stack web dashboard with live GPS/GeoJSON export and $>70\%$ herbicide savings proof.
- [ ] **Milestone 4 (Week 4):** Final thesis monograph compiled with Typst and empirical benchmark graphs.
