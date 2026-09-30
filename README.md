# 🌱 AgriAgent: Autonomous Dual-Brain Multi-Agent Vision Framework for Zero-Shot Precision Agriculture

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Grounding DINO](https://img.shields.io/badge/Detection-Grounding%20DINO--T-green.svg)](https://github.com/IDEA-Research/Grounding-DINO)
[![SAM 2](https://img.shields.io/badge/Segmentation-SAM%202--Tiny-purple.svg)](https://github.com/facebookresearch/sam2)
[![Institution](https://img.shields.io/badge/Institution-VJTI%20Mumbai-red.svg)](https://vjti.ac.in/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Final Year B.Tech Engineering Project (4 Credits) · Academic Year 2025–2026**  
> **Department of Computer Engineering, Veermata Jijabai Technological Institute (VJTI), Mumbai**  
> **Project Guide:** Prof. V. D. Dhore  
> **Repository:** [https://github.com/Chaitanya-666/agriAgent](https://github.com/Chaitanya-666/agriAgent)  
> **Official Proposal & Monograph:** [`docs/AgriAgent_Master_Project_Proposal.pdf`](docs/AgriAgent_Master_Project_Proposal.pdf)

---

## 📌 Executive Summary

Modern agriculture relies heavily on **broadcast chemical spraying**—dousing entire acreages with uniform doses of herbicides and pesticides. According to field agronomy studies, up to **76% of broadcast chemicals fall onto bare soil or healthy crops**, causing severe chemical runoff, groundwater contamination, herbicide-resistant weeds, and immense economic burden for farmers.

While computer vision promises targeted spot-spraying, conventional supervised models (YOLO, U-Net, DeepLabV3) suffer from **severe domain generalization collapse**:
* A model trained in Europe on German sugar beets fails when deployed to Indian cotton fields (*Gossypium hirsutum*) due to differences in leaf shape, soil appearance, and regional weed biotypes (*Parthenium*, *Amaranthus*).
* Retraining models for every regional crop requires expensive, labor-intensive pixel-level annotations.

**AgriAgent solves this through a zero-shot, open-vocabulary multi-agent architecture:**
A farmer or agronomist uploads an ordinary field photo (from a smartphone or drone) and enters a natural language command:  
> *"Find all weeds and spare the cotton plants"* or *"Locate yellow disease lesions"*.

AgriAgent localizes target regions, computes pixel-accurate masks, executes an automated heuristic error-correction loop, and generates a **precision spray map** that **reduces herbicide volume by over 70%** without any task-specific retraining.

---

## 🧠 The Architectural Innovation: Dual-Brain Multi-Agent Engine

Existing multi-agent frameworks (LangGraph, AutoGen) route every internal micro-step through heavy frontier LLMs, causing **8–10 second latency**, massive API costs, and context overflows when segmentations are dumped into chat histories.

AgriAgent introduces a **Dual-Brain Cognitive Architecture**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AgriAgent Dual-Brain Framework                        │
├──────────────────────────────────────┬──────────────────────────────────────┤
│    SYSTEM 1: Fast & Deterministic    │   SYSTEM 2: Deliberative & Agronomic │
│         (Laya / Jev Principles)      │          (Groq Llama-3.3-70B)        │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ • Latency: < 40ms (Single parallel)  │ • Latency: 1.5 – 3.0s                │
│ • Typed schema intent routing        │ • Deep agronomic reasoning & advice  │
│ • Refinement gating (IoU < 0.85)     │ • Multimodal VLM (Qwen2.5-VL /       │
│ • Safety buffer boundary validation  │   Florence-2) for lesion diagnosis   │
│ • Chemical dosage limit guardrails   │ • ChromaDB RAG across ICAR compendiums│
└──────────────────────────────────────┴──────────────────────────────────────┘
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │               ZERO-SHOT VISION FOUNDATION              │
      ├────────────────────────────┬───────────────────────────┤
      │ Grounding DINO-T / 1.5     │ SAM 2-Tiny (Hiera ViT)    │
      │ Open-vocabulary bounding   │ Promptable instance mask  │
      │ boxes from text queries    │ generation (< 125ms)      │
      └────────────────────────────┴───────────────────────────┘
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │             HEURISTIC REFINEMENT LOOP                  │
      │  Boundary error centroid calculation (Under / Over-    │
      │  segmentation) with corrective prompt point injection  │
      └────────────────────────────────────────────────────────┘
```

1. **System 1 (Fast Deterministic Decision & Triage Layer):**
   * Inspired by modern non-generative "System One" decision models like *Jev* (TypeSafe AI) and open-source *Laya* (ConvAI Innovations, Apache 2.0).
   * Runs in **$<40\text{ ms}$** without token generation, mapping user queries to typed schemas (`TaskRoute.WEED_SPRAYING`, `TaskRoute.PEST_AUDITING`), gating refinement triggers, and checking safety buffers.
2. **System 2 (Deliberative Agronomic Intelligence & RAG):**
   * Groq-accelerated Llama-3.3-70B and multimodal vision models (Qwen2.5-VL / Florence-2).
   * Ingests official manuals from the **Indian Council of Agricultural Research (ICAR)** and **Central Insecticide Board & Registration Committee (CIBRC)** via ChromaDB to synthesize actionable prescriptions.
3. **Zero-Shot Vision Engine:**
   * **Grounding DINO-T:** Swin-T + BERT text-image cross-attention for open-vocabulary box detection.
   * **SAM 2-Tiny:** Hierarchical Hiera ViT producing dense binary masks and predicted IoU scores in $<125\text{ ms}$ on a free Google Colab T4 GPU.
   * **Refinement Engine:** Deterministic error centroid calculation detecting under- or over-segmentation and injecting corrective prompt points back into SAM 2 (capped at 2 iterations).

---

## 🚜 5 Agricultural Applications, 1 Unified Pipeline

Configured dynamically via [`config/prompts.yaml`](config/prompts.yaml) without code changes:

| # | Application Domain | Natural Language Prompt | Target Outputs | Target Benchmark |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Site-Specific Weed Spraying** | `"weed. crop."` | Weed vs crop masks, spray contours, $>70\%$ herbicide savings | SugarBeets 2016, CottonWeeds |
| **2** | **Disease & Pest Lesion Auditing** | `"diseased leaf. spot. lesion."` | Lesion area ratio (%), severity grading, ICAR treatment card | PlantDoc, Cotton Leaf Disease |
| **3** | **Yield Estimation / Fruit Count** | `"wheat head."` or `"fruit."` | Instance count, size distribution histogram, yield forecast | GWHD 2021 |
| **4** | **Canopy Coverage & Stand Count**| `"crop. bare soil. gap."` | Foliage vegetation ratio, germination gap alerts with GPS | SugarBeets UGV, Drone imagery |
| **5** | **Nutrient Stress (Chlorosis)** | `"yellow leaf. stressed leaf."` | Nitrogen/Iron chlorosis heatmap, fertilizer recommendation | PlantDoc, Cotton field photos |

---

## 🏗️ Heritage: SmartDesk Multi-Agent Refactoring

AgriAgent builds directly upon the architectural foundation of **SmartDesk**, a multi-agent productivity orchestrator authored by team members:

* **Pruned Components:** Removed personal desktop tools (Gmail SMTP, Google Calendar, Telegram bot, local terminal execution) which are irrelevant to agricultural edge systems.
* **Preserved & Specialized Signatures:**
  * **LangGraph Orchestrator:** Supervisor-worker state machine directing multi-agent handoffs.
  * **Clean Slate Finalizers (`RemoveMessage`):** Cleans all intermediate reasoning tokens between successive field image runs, preventing visual context bleeding in batch processing.
  * **Typed `Artifact` Subsystem:** Stores large 2D numpy mask arrays and GeoTIFF spray rasters as external typed artifacts (`VISION_MASK`, `SPRAY_MAP`), keeping the LLM context window pristine.
  * **ChromaDB Agronomy RAG:** Redirected vector store to index ICAR crop protection manuals and CIBRC chemical registration databases.

---

## 👥 Balanced Team Allocation & Contribution Matrix

To ensure equal academic rigor and strong viva defense, the project is structured into four distinct, equally weighted engineering tracks:

```
                      ┌───────────────────────────────────────────────┐
                      │            AgriAgent Architecture             │
                      └──────────────────────┬────────────────────────┘
                                             │
           ┌───────────────────┬─────────────┴───────┬───────────────────┐
           │                   │                     │                   │
           ▼                   ▼                     ▼                   ▼
  ┌─────────────────┐ ┌─────────────────┐   ┌─────────────────┐ ┌─────────────────┐
  │ Track 1 (LOCKED)│ │ Track 2 (Review)│   │ Track 3 (Review)│ │ Track 4 (Review)│
  │ Chaitanya Shinde│ │   Amit Ingle    │   │  Sahil Chavan   │ │  Sumant Vetal   │
  │ Lead AI Engine  │ │ Multimodal VLM  │   │ Data & Benchmark│ │ Geospatial & UI │
  └─────────────────┘ └─────────────────┘   └─────────────────┘ └─────────────────┘
```

* **Track 1 — Core AI & Vision Systems (LOCKED: Chaitanya Shinde):**
  * Grounding DINO + SAM 2 pipeline inference wrappers (`src/vision/`).
  * System-1 Fast Decision Engine (Laya / Jev routing & safety guardrails).
  * Deterministic IoU Refinement Engine (`refinement.py`) and FP16 memory optimization.
  * LangGraph state schema & SmartDesk core refactoring.
* **Track 2 — Multimodal VLM & Agronomy Intelligence (Candidate: Amit Ingle):**
  * Multimodal visual reasoning with Qwen2.5-VL / Florence-2 for lesion diagnosis.
  * ICAR & CIBRC Agronomy RAG vector pipeline in ChromaDB.
  * Contextual farmer prescription generator and VLM vs Heuristic ablation study.
* **Track 3 — Data Science & Empirical Benchmarking (Candidate: Sahil Chavan):**
  * Dataset curation (Kaggle Indian CottonWeeds, Cotton Pests, SugarBeets 2016).
  * Quantitative evaluation test harness ([`src/evaluation/iou_dice.py`](src/evaluation/iou_dice.py)).
  * Statistical significance testing (bootstrapped 95% CIs, paired t-tests) and benchmark tables.
* **Track 4 — Geospatial Systems & Full-Stack Deployment (Candidate: Sumant Vetal):**
  * Production Streamlit Dashboard ([`app/app.py`](app/app.py)).
  * Real-time OpenCV / Supervision mask overlay compositor.
  * Geospatial spray-map generator (GeoJSON / GPS drone coordinates).
  * Automated prescription PDF / CSV report generator.

> *Note:* Track 1 is locked. Tracks 2, 3, and 4 are open for team review and will be confirmed if no grievances are raised.

---

## 📁 Repository Structure

```text
AgriAgent/
├── README.md                          # Project documentation and architecture guide
├── CONTEXT.md                         # Problem, solution, and tech stack overview
├── AI_MEMORY.md                       # Engineering session memory and state log
├── requirements.txt                   # Production Python dependencies
│
├── config/
│   ├── prompts.yaml                   # Text prompts across 5 agricultural applications
│   ├── thresholds.yaml                # Quality thresholds (IoU 0.85, buffer 5-10cm)
│   └── model_config.yaml              # Model paths, FP16 precision, device selection
│
├── src/
│   ├── state.py                       # Extended GraphState with Typed Artifacts
│   ├── llm_factory.py                 # Groq API / local LLM switch
│   ├── graph.py                       # LangGraph StateGraph pipeline
│   ├── orchestrator.py                # Dual-brain supervisor node logic
│   │
│   ├── agents/                        # LangGraph Agent Nodes
│   │   ├── grounding_agent.py         # Grounding DINO detector node
│   │   ├── segmentation_agent.py      # SAM 2 instance segmenter node
│   │   ├── analysis_agent.py          # Refinement trigger & savings calculator
│   │   ├── agronomy_agent.py          # ICAR RAG & VLM reasoning agent
│   │   └── smartdesk_agents/          # Preserved SmartDesk modular sub-agents
│   │
│   ├── vision/                        # Core AI Inference & Heuristics
│   │   ├── grounding_dino.py          # Grounding DINO HuggingFace wrapper
│   │   ├── sam2_wrapper.py            # SAM 2 predictor wrapper (box & point prompts)
│   │   ├── refinement.py              # IoU error centroid refinement loop
│   │   └── visualization.py           # Real-time mask overlay and spray rendering
│   │
│   └── evaluation/                    # Scientific Benchmarking
│       ├── iou_dice.py                # IoU, Dice, and Herbicide savings % math
│       └── detection_metrics.py       # mAP@0.5 and statistical bootstrapping
│
├── app/                               # Full-Stack Streamlit Application
│   ├── app.py                         # Streamlit entry point
│   └── components/                    # Modular UI components (upload, spray map, cards)
│
├── data/
│   ├── datasets/                      # Benchmark datasets (SugarBeets, CottonWeeds)
│   ├── knowledge_base/                # ICAR / CIBRC crop protection manuals (PDF/MD)
│   └── outputs/                       # Exported spray maps and prescription PDFs
│
└── docs/                              # Academic Specifications & Publications
    ├── AgriAgent_Master_Project_Proposal.pdf # 6-page compiled formal monograph
    ├── AgriAgent_Master_Project_Proposal.typ # Typst publication source code
    └── Qwen_Dossier/                  # Feasibility dossiers and research catalogs
```

---

## ⚡ Quickstart & Installation

### 1. Environment Setup
```bash
# Clone the repository
git clone https://github.com/Chaitanya-666/agriAgent.git
cd agriAgent

# Create and activate Python 3.10+ virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_groq_api_key_here
HF_TOKEN=your_huggingface_token_here
```

### 3. Launch the Streamlit Portal
```bash
streamlit run app/app.py
```

---

## 🎯 Target Publication & Milestones

* **Target Academic Venue:** 7th International Agriculture-Vision Workshop (CVPR 2026) / MDPI AgriEngineering.
* **Key Milestone:** Tuesday Progress Presentation with Project Supervisor **Prof. V. D. Dhore**, VJTI Mumbai.

