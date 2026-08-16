# AgriAgent - Project Context

## What Is This?
AgriAgent is a Final Year Project (FYP) that builds an autonomous multi-agent
vision framework for zero-shot agricultural image analysis. It extends the
SmartDesk multi-agent system with computer vision capabilities.

## The Problem
Current agricultural AI requires expensive retraining for every new crop-weed
combination. A model trained on German sugar beet fields fails on Indian cotton
fields. This prevents scalable adoption of precision agriculture.

## Our Solution
We use Grounding DINO (open-vocabulary detection) + SAM 2 (promptable
segmentation) in a LangGraph multi-agent pipeline. The farmer types a natural
language command ("find all weeds"), and the system segments them WITHOUT any
retraining.

## Key Innovation
1. Zero-shot: No task-specific training required
2. Multi-agent: LangGraph orchestrates specialized vision agents
3. Refinement loop: IoU-based heuristic correction (inspired by MedSAM-Agent)
4. 5 applications, 1 pipeline: Same code, different prompts
5. Actionable output: Spray maps with herbicide savings %

## Tech Stack
- LangGraph (orchestration)
- Grounding DINO-T (detection)
- SAM 2-Tiny (segmentation)
- Groq API / Llama-3 (LLM reasoning)
- ChromaDB (RAG knowledge base)
- Streamlit (UI)

## Team
- Member 1: Architect / Orchestrator
- Member 2: Vision Pipeline Engineer
- Member 3: Data & Evaluation Lead
- Member 4: UI / Demo Engineer

## Instructor
Prof. V. D. Dhore

## Academic Year
2025-26
