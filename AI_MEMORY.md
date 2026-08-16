# AgriAgent AI Project Memory & Context

## Project Overview
**AgriAgent** is an autonomous multi-agent vision framework for precision agriculture, designed as a Final Year Project (FYP) for 2025-26. It extends the **SmartDesk** multi-agent orchestrator by adding computer vision capabilities via **LangGraph**, **Grounding DINO-T** (for zero-shot detection), and **SAM 2-Tiny** (for promptable segmentation).

## Current Status (End of Session - August 16, 2026)
- **Base Scaffold setup:** The base scaffold from `base_resources/AgriAgent_Package/05_Repo_Scaffold` has been successfully copied into the root directory.
- **SmartDesk Integration:** The cloned `SmartDesk` repo has been archived to `docs/SmartDesk_Original_Repo`, and its core agents (`workspace_agent.py`, `knowledge_agent.py`, `productivity_agent.py`) were extracted to `src/agents/smartdesk_agents/` for integration.
- **Directory Structure:** Foundational directories (`src`, `data`, `config`, `docs`, `tests`, `app`, `notebooks`, `scripts`) are populated.
- **Documentation Organized:** 
  - PDFs/Research papers moved to `docs/research_papers/`.
  - Qwen Dossier moved to `docs/Qwen_Dossier/`.
  - Verified Links and BibTeX files correctly filed under `docs/verified_resources/` and `docs/paper/`.
- **Datasets & Models:** Relevant dataset download links and HuggingFace model endpoints are stored in `data/datasets/DATASETS_LINKS.md` and `data/models/MODELS_LINKS.md`.
- **Configurations:** `prompts.yaml`, `thresholds.yaml`, and the extended `state.py` are properly placed.

## Architectural Notes to Remember
- **Orchestration:** Driven by LangGraph using the `GraphState` defined in `src/state.py`.
- **Refinement Loop:** Uses a deterministic numpy-based IoU error centroid calculation (inspired by MedSAM-Agent) to handle low-IoU cases. Found in `src/vision/refinement.py`.
- **Target Venues:** CVPR Agriculture-Vision Workshop 2026.
- **Goal Metric:** Maximize Herbicide savings (target: 76%) using precision spray maps.

## Next Action Items (For Next Session)
1. Write the LangGraph nodes for the **Grounding Agent** and **Segmentation Agent**.
2. Create the Python wrapper scripts for **Grounding DINO** and **SAM 2** inference under `src/vision/`.
3. Integrate the Orchestrator routing to delegate tasks between the SmartDesk tools and the new vision pipeline.
4. Download a sample of the SugarBeets 2016 dataset to validate the vision pipeline end-to-end locally.
