"""
src/workflow.py
Central System-1 Reflex Workflow Orchestrator for AgriAgent.

Architecture Rationale:
-----------------------
Orchestrates the fast visual reflex loop (<40 ms target on edge hardware):
  [Input Image] 
       │
       ▼
  [Detection Node (Grounding DINO)] 
       │
       ▼
  [Segmentation Node (SAM 2)] 
       │
       ▼
  [Active Refinement Loop (IoU < 0.85, max 2 iterations)]
       │
       ▼
  [Spray Map & Agronomic Savings Compositor]
       │
       ▼
  [GraphState Output & Spray Artifacts]

Design & Resilience:
--------------------
Provides a dual-execution architecture:
1. Direct Native State Machine (`VisionWorkflowRunner`):
   Executes the exact DAG without external framework dependencies, ensuring
   rock-solid local testing, zero-dependency CI runs, and lightweight deployment.
2. LangGraph StateGraph Compilation (`create_langgraph_workflow()`):
   When `langgraph` is installed, compiles the identical nodes and conditional
   edges into an official LangGraph executable graph with state checkpointing.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from PIL import Image

from src.state import Artifact, ArtifactType, Box, GraphState, Mask
from src.vision.grounding_dino import GroundingDINOEngine
from src.vision.sam2_wrapper import SAM2Segmenter
from src.vision.refinement import get_refinement_point
from src.evaluation.iou_dice import compute_herbicide_savings
from src.agents.laya_router import LayaTriageRouter

logger = logging.getLogger("agriagent.workflow")


class VisionWorkflowRunner:
    """
    Production orchestrator for AgriAgent System-1 visual reasoning.
    
    Coordinates zero-shot detection, instance segmentation, closed-loop
    error-centroid refinement, Laya-based triage, and herbicide savings calculation.
    """

    def __init__(
        self,
        detector: Optional[GroundingDINOEngine] = None,
        segmenter: Optional[SAM2Segmenter] = None,
        laya_router: Optional[LayaTriageRouter] = None,
        iou_threshold: float = 0.85,
        max_refinements: int = 2,
        buffer_pixels: int = 10,
        mock_mode: bool = False,
        system2: Optional[Any] = None,
    ):
        self.mock_mode = mock_mode
        self.detector = detector or GroundingDINOEngine(mock_mode=mock_mode)
        self.segmenter = segmenter or SAM2Segmenter(mock_mode=mock_mode)
        self.laya_router = laya_router or LayaTriageRouter()
        if system2 is not None:
            self.system2 = system2
        else:
            try:
                from src.agronomy.system2_node import System2Reasoner
                self.system2 = System2Reasoner(mock_mode=mock_mode)
            except Exception as e:
                logger.debug("System2Reasoner unavailable: %s", e)
                self.system2 = None
        self.iou_threshold = iou_threshold
        self.max_refinements = max_refinements
        self.buffer_pixels = buffer_pixels

    def detect_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 1: Execute zero-shot detection using Grounding DINO."""
        img = state.get("image") or state.get("image_path")
        if img is None:
            return {"error": "Missing input image in GraphState.", "boxes": []}

        prompt = state.get("text_prompt") or "cotton weed . broadleaf plant ."
        boxes = self.detector.detect_to_state_boxes(img, text_prompt=prompt)
        logger.info("VisionWorkflow: Detected %d candidate boxes.", len(boxes))
        return {"boxes": boxes}

    def segment_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 2: Convert candidate boxes into pixel-accurate SAM 2 binary masks."""
        img = state.get("image") or state.get("image_path")
        boxes = state.get("boxes", [])

        if not boxes:
            logger.info("VisionWorkflow: No bounding boxes to segment.")
            return {"masks": []}

        masks = self.segmenter.segment_to_state_masks(img, boxes)
        logger.info("VisionWorkflow: Segmented %d instance masks.", len(masks))
        return {"masks": masks}

    def refine_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 3: Active closed-loop refinement via error centroid point prompting."""
        img = state.get("image") or state.get("image_path")
        masks = state.get("masks", [])
        refinement_count = state.get("refinement_count", 0)

        if refinement_count >= self.max_refinements:
            return {"refinement_count": refinement_count}

        updated_masks: List[Mask] = []
        refined_any = False

        for mask_dict in masks:
            current_iou = mask_dict.get("predicted_iou", 1.0)
            box = mask_dict["box"]
            area_px = int(mask_dict["mask_array"].sum())
            label = box.get("label", "weed")

            needs_refine = self.laya_router.evaluate_mask_refinement(
                current_iou, area_px, label, threshold=self.iou_threshold
            )

            if needs_refine and refinement_count < self.max_refinements:
                # Calculate geometric error centroid
                box_coords = (box["x1"], box["y1"], box["x2"], box["y2"])
                pt = get_refinement_point(
                    mask_dict["mask_array"],
                    box_coords,
                    predicted_iou=current_iou,
                    threshold=self.iou_threshold,
                )

                if pt is not None:
                    # Query SAM 2 with corrective point
                    refined_res = self.segmenter.refine_with_point(
                        img, box, mask_dict["mask_array"], pt
                    )
                    updated_masks.append(refined_res.to_dict())
                    refined_any = True
                    logger.info(
                        "VisionWorkflow: Refined mask for '%s' (IoU: %.2f -> %.2f)",
                        box.get("label", "weed"),
                        current_iou,
                        refined_res.predicted_iou,
                    )
                    continue

            updated_masks.append(mask_dict)

        new_count = refinement_count + (1 if refined_any else 0)
        return {"masks": updated_masks, "refinement_count": new_count}

    def spray_map_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 4: Compute composite spray prescription, weed coverage %, and herbicide savings %."""
        masks = state.get("masks", [])
        img = state.get("image")

        if isinstance(img, Image.Image):
            h, w = img.size[1], img.size[0]
        else:
            # Fallback dimensions
            h, w = (480, 640)

        composite_mask = np.zeros((h, w), dtype=bool)
        for m in masks:
            composite_mask |= m["mask_array"]

        weed_pixel_count = int(composite_mask.sum())
        total_pixels = h * w
        infestation_pct = round((weed_pixel_count / total_pixels) * 100.0, 2)

        chemical_savings_pct = compute_herbicide_savings(
            composite_mask, (h, w), buffer_pixels=self.buffer_pixels
        )

        spray_map_data = {
            "infestation_percentage": infestation_pct,
            "chemical_savings_percentage": round(chemical_savings_pct, 2),
            "weed_count": len(masks),
            "buffer_pixels": self.buffer_pixels,
            "target_resolution": {"width": w, "height": h},
            "status": "Selective Spot-Spray Prescription Generated",
        }

        # Build serializable artifact
        spray_artifact = Artifact(
            id="spray_prescription_01",
            type=ArtifactType.SPRAY_MAP,
            title="Precision Herbicide Spray Map",
            description=f"Generated prescription saving {chemical_savings_pct:.1f}% chemical volume.",
            metadata=spray_map_data,
            payload={"composite_mask": composite_mask},
        )

        artifacts = state.get("artifacts", {}).copy()
        artifacts["spray_map"] = spray_artifact

        logger.info(
            "VisionWorkflow: Generated spray map (Infestation: %.1f%%, Chemical Savings: %.1f%%)",
            infestation_pct,
            chemical_savings_pct,
        )

        return {
            "spray_map": spray_map_data,
            "artifacts": artifacts,
        }

    def run(self, initial_state: GraphState) -> GraphState:
        """
        Execute the complete reflex state machine sequentially.
        
        Args:
            initial_state: GraphState initialized with image and text_prompt.

        Returns:
            GraphState: Fully populated state containing boxes, masks, and spray_map.
        """
        state = initial_state.copy()
        state.setdefault("refinement_count", 0)
        state.setdefault("artifacts", {})
        state.setdefault("messages", [])

        # 1. Detection
        det_out = self.detect_node(state)
        state.update(det_out)
        if state.get("error"):
            return state

        # 2. Segmentation
        seg_out = self.segment_node(state)
        state.update(seg_out)

        # 3. Closed-Loop Refinement (conditional loop)
        for _ in range(self.max_refinements):
            # Check if any mask qualifies for refinement
            needs_refine = any(
                m.get("predicted_iou", 1.0) < self.iou_threshold
                for m in state.get("masks", [])
            )
            if not needs_refine:
                break
            ref_out = self.refine_node(state)
            state.update(ref_out)

        # 4. Spray Map Generation
        spray_out = self.spray_map_node(state)
        state.update(spray_out)

        # 5. System-1 vs System-2 Laya Triage Arbitration
        for b, m in zip(state.get("boxes", []), state.get("masks", [])):
            escalate, reason = self.laya_router.evaluate_system2_escalation(
                b.get("score", 1.0), b.get("label", "weed"), m.get("predicted_iou", 1.0)
            )
            if escalate:
                state["system2_needed"] = True
                state["vlm_reasoning"] = f"Laya Triage Alert: {reason}"
                break

        if state.get("system2_needed") and self.system2 is not None:
            state.update(self.system2.system2_node(state))
        
        return state


def create_initial_state(
    image: Image.Image,
    text_prompt: str = "cotton weed . broadleaf plant .",
    image_path: Optional[str] = None,
) -> GraphState:
    """Helper to instantiate a clean, properly typed initial GraphState."""
    return {
        "messages": [],
        "artifacts": {},
        "error": None,
        "image": image,
        "image_path": image_path,
        "text_prompt": text_prompt,
        "field_metadata": {},
        "boxes": [],
        "masks": [],
        "refinement_count": 0,
        "system2_needed": False,
        "vlm_reasoning": None,
        "prescription_report": None,
        "spray_map": None,
        "ground_truth_masks": None,
        "evaluation_metrics": None,
    }


def create_langgraph_workflow(runner: Optional[VisionWorkflowRunner] = None):
    """
    Compiles the workflow into an official LangGraph StateGraph instance.
    Raises ImportError if langgraph is not installed in the active environment.
    """
    from langgraph.graph import StateGraph, START, END

    wf_runner = runner or VisionWorkflowRunner()
    builder = StateGraph(GraphState)

    builder.add_node("detect", wf_runner.detect_node)
    builder.add_node("segment", wf_runner.segment_node)
    builder.add_node("refine", wf_runner.refine_node)
    builder.add_node("spray_map", wf_runner.spray_map_node)

    builder.add_edge(START, "detect")
    builder.add_edge("detect", "segment")

    def should_refine_edge(state: GraphState) -> str:
        count = state.get("refinement_count", 0)
        if count >= wf_runner.max_refinements:
            return "spray_map"
        for m in state.get("masks", []):
            if m.get("predicted_iou", 1.0) < wf_runner.iou_threshold:
                return "refine"
        return "spray_map"

    builder.add_conditional_edges(
        "segment",
        should_refine_edge,
        {"refine": "refine", "spray_map": "spray_map"}
    )
    builder.add_edge("refine", "spray_map")
    builder.add_edge("spray_map", END)

    return builder.compile()
