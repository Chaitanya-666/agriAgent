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
- [/] **Task 1.1:** Build `src/vision/grounding_dino.py`:
  - [x] Zero-shot open-vocabulary bounding box detector interface.
  - [x] Hugging Face / IDEA-Research model loader (`IDEA-Research/grounding-dino-tiny`).
  - [x] Deterministic mock fallback mode (`mock_mode=True`) for lightweight CPU/laptop testing.
  - [ ] Standalone test & verification script.
- [ ] **Task 1.2:** Build `src/vision/sam2_wrapper.py`:
  - [ ] Meta AI SAM 2 promptable mask generator wrapper.
  - [ ] Bounding-box-to-mask conversion (`predict_masks(image, boxes)`).
  - [ ] Deterministic mock fallback mode for fast local verification.
- [ ] **Task 1.3:** Connect `src/vision/refinement.py` closed-loop logic:
  - [ ] Active IoU threshold evaluation ($\text{IoU} < 0.85$).
  - [ ] Error centroid calculation for point prompt correction.
- [ ] **Task 1.4:** Build `src/workflow.py` LangGraph state graph linking System-1 vision reflex nodes.
- [ ] **Task 1.5:** Create end-to-end test verification in `tests/test_vision_pipeline.py`.

---

### 🌾 Track 2: Multimodal VLM & Agronomy Intelligence
**Owner:** Sumant Vetal (`sumant/vlm-agronomy`)
- [ ] **Task 2.1:** Evaluate Qwen2.5-VL-7B or Florence-2 for visual reasoning on field photos (`notebooks/01_vlm_reasoning_experiment.ipynb`).
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
