"""
src/agronomy/system2_node.py
System-2 node: VLM diagnosis -> RAG prescription. Plugs into VisionWorkflowRunner / LangGraph.
Fills GraphState.vlm_reasoning, GraphState.prescription_report and an Artifact.
"""

import logging
from typing import Any, Dict, Optional

from src.agronomy.knowledge_store import InMemoryKnowledgeStore
from src.agronomy.prescription import get_herbicide_prescription
from src.agronomy.vlm_critic import VLMCritic
from src.state import Artifact, ArtifactType, GraphState

logger = logging.getLogger("agriagent.system2")


class System2Reasoner:
    def __init__(self, critic: Optional[VLMCritic] = None, store=None, mock_mode: bool = False):
        self.critic = critic or VLMCritic(mock_mode=mock_mode)
        if store is None:
            # Herbicide advice comes from the ICAR table rows transcribed with page numbers
            # (CANONICAL_ICAR_TABLE_ROWS), in mock and real mode alike. The ChromaDB store was
            # never filled, so every real-mode lookup returned "no_knowledge_found", and its
            # raw PDF chunks carry no structured dose to prescribe from.
            store = InMemoryKnowledgeStore()
            store.ingest()
        self.store = store

    def system2_node(self, state: GraphState) -> Dict[str, Any]:
        img = state.get("image")
        if img is None:
            return {"error": "System-2 needs an in-memory PIL image."}
        crop = (state.get("field_metadata") or {}).get("crop", "cotton")
        diag = self.critic.diagnose(img, crop_hint=crop)
        weed = diag.get("weed_or_disease", "unknown weed")
        stage = diag.get("crop_stage", "vegetative")
        # The farmer's declared crop decides which herbicides are legal; the VLM's guess must not
        # (on 17 Oct Groq called a sugar beet field "cotton"). A disagreement is reported instead.
        report = get_herbicide_prescription(weed, stage, crop=crop, store=self.store)
        report["vlm_diagnosis"] = diag
        seen_crop = str(diag.get("crop", "")).strip().lower()
        if seen_crop and seen_crop.replace(" ", "") != str(crop).strip().lower().replace(" ", ""):
            report["crop_mismatch_warning"] = (
                f"The VLM saw '{seen_crop}' but the field is declared as '{crop}'. "
                "The prescription follows the declared crop; check the photo."
            )

        artifacts = dict(state.get("artifacts", {}))
        artifacts["prescription_report"] = Artifact(
            id="prescription_report_01",
            type=ArtifactType.PRESCRIPTION_REPORT,
            title="ICAR/CIBRC Weed Prescription",
            description=diag.get("explanation", ""),
            metadata={"status": report["status"]},
            payload=report,
        )
        logger.info("System2: %s @ %s -> %s", weed, stage, report["status"])
        return {
            "vlm_reasoning": diag.get("explanation", ""),
            "prescription_report": report,
            "artifacts": artifacts,
        }
