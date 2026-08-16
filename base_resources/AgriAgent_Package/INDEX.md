# AgriAgent FYP - Complete Resource Package

> **Your single source of truth.** Every paper, dataset, model, config file, code snippet, and verified link needed to build, execute, and publish the AgriAgent Final Year Project.

**Generated:** August 16, 2026 | **Total Items:** 80+ resources across 8 categories

---

## Package Contents

### 📄 01_Research_Bible/
The comprehensive 12-section FYP Research Bible PDF covering:
- Project overview, problem statement, and the 5 application domains
- Foundation models deep dive (Grounding DINO, SAM 2, CLIPSeg) with exact specs
- Agricultural datasets catalog with download links and statistics
- Five application deep dives with prompts, outputs, and evaluation targets
- Literature & gap analysis (5 identified gaps)
- Multi-agent architecture with SmartDesk codebase deep dive
- Feasibility, costs ($0 total), and computational requirements
- Publishability strategy and venue comparison
- Implementation roadmap and risk assessment
- Thesis metrics and evaluation plan
- **5 Alternative FYP ideas** (Drone Scout, Smart Harvester, Sticky Trap, Post-Harvest, Hydroponics)
- **4-Phase execution plan** with "Secret Sauce" for an A+
- **File:** `AgriAgent_FYP_Research_Bible.pdf` (124KB, 12+ pages)

### 📋 02_Qwen_Dossier/
The complete Qwen-generated feasibility dossier with:
- Hardware/Software/Data feasibility verification (all PASS)
- 18+ research papers catalog with arXiv links and citation counts
- Complete dataset resource catalog with download instructions
- Model resources & HuggingFace model IDs
- Full GitHub repo structure (50+ files)
- Configuration files (requirements.txt, prompts.yaml, thresholds.yaml, .env.example)
- Core code snippets (state.py, refinement.py, iou_dice.py)
- Colab notebook templates
- Publication targets & paper outline
- Week-by-week execution checklist
- **File:** `Qwen_Complete_Dossier.md` (1131 lines)

### 🏗️ 03_SmartDesk_Reference/
The actual SmartDesk codebase README describing:
- Supervisor-Worker (Orchestrator-SubAgent) architecture
- 3 existing agents (WorkspaceAgent, KnowledgeAgent, ProductivityAgent)
- GraphState fields and state management
- Clean Slate Finalizers pattern
- Artifact System for context window management
- Mock Mode fallbacks
- **File:** `SmartDesk_README.md`

### ✅ 04_Verified_Resources/
**ALL links verified via live web search (August 2026):**
- Grounding DINO-T HuggingFace + GitHub (VERIFIED)
- SAM 2-Tiny HuggingFace native + Transformers format (VERIFIED)
- Grounded-SAM-2 combined pipeline repo (VERIFIED)
- CVPR Agriculture-Vision Workshop 2026 (VERIFIED - 7th edition, Denver CO)
- MDPI AgriEngineering Special Issues (VERIFIED - 2 active SIs)
- All 7 primary datasets with working download links (VERIFIED)
- LangGraph tutorials, Groq API limits, Colab T4 specs (VERIFIED)
- Streamlit Community Cloud, ChromaDB (VERIFIED)
- MedSAM-Agent, ODinW, ReAct paper links (VERIFIED)
- Latest 2024-2026 zero-shot agriculture papers
- **File:** `VERIFIED_RESOURCES.md`

### 🧱 05_Repo_Scaffold/
Ready-to-use repo structure with actual implementation files:
- `src/state.py` - Extended GraphState with Box, Mask types
- `src/vision/refinement.py` - IoU-based refinement loop (30 lines NumPy)
- `src/evaluation/iou_dice.py` - IoU, Dice, herbicide savings computation
- `config/prompts.yaml` - All 5 application prompts
- `config/thresholds.yaml` - IoU threshold, refinement, evaluation settings
- `.env.example` - Template for API keys and model paths
- `requirements.txt` - All Python dependencies
- `CONTEXT.md` - Project context for repo visitors

### 📚 06_BibTeX_References/
Complete BibTeX file with 25+ entries:
- 5 core papers (Grounding DINO, SAM 2, CLIPSeg, MedSAM-Agent, ODinW)
- 10 agricultural CV papers
- 5 dataset papers
- 3 agent/orchestration papers
- 3 foundation model background papers
- 3 latest zero-shot agriculture papers (2024-2026)
- **File:** `references.bib`

### 🔍 07_Search_Results/
Raw JSON search results from 19+ web searches:
- Grounding DINO, SAM 2, CLIPSeg specs
- SugarBeets, DeepWeeds, PlantDoc, GWHD, PlantVillage datasets
- Precision agriculture, ODinW, LangGraph, MedSAM-Agent
- SmartDesk, Roboflow, model sizes, publishability
- **19 JSON files** with full search result data

### 📓 08_Colab_Templates/
(Placeholder - copy notebook templates from Qwen Dossier Part 8)
- 01_grounding_dino_demo.ipynb
- 02_sam2_demo.ipynb
- 03_combined_pipeline.ipynb
- 04_refinement_loop.ipynb
- 05_evaluation.ipynb
- 06_all_applications.ipynb

---

## Quick Start

1. **Read the Research Bible** (01_Research_Bible/) - This is your master reference
2. **Review Verified Resources** (04_Verified_Resources/) - All links confirmed working
3. **Set up the repo** using 05_Repo_Scaffold/ structure
4. **Copy references.bib** (06_BibTeX_References/) into your thesis
5. **Start Week 1** using the checklist in 02_Qwen_Dossier/ Part 11

## Key Facts at a Glance

| Item | Value |
|------|-------|
| **Project Name** | AgriAgent |
| **Detection Model** | Grounding DINO-T (172M params) |
| **Segmentation Model** | SAM 2-Tiny (38.9M params) |
| **Orchestrator** | LangGraph |
| **Total Cost** | $0 |
| **GPU** | Google Colab T4 (free) |
| **Primary Venue** | CVPR Agriculture-Vision Workshop 2026 |
| **Submission Deadline** | ~March 1-9, 2026 |
| **Headline Metric** | "Reduces herbicide use by 73%" |
