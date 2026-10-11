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
  [Active Refinement Loop (IoU < 0.85, max 2 iterations)] ◄───┐ (Cyclic recursion)
       │                                                      │
       ├──────────────────────────────────────────────────────┘
       ▼
  [Spray Map & Agronomic Savings Compositor]
       │
       ▼
  [System-1 vs System-2 Triage Arbitration]
       │
       ├─────────────────────────┐
       ▼ (if escalated)          ▼ (standard reflex)
  [System-2 Deliberative Brain] [GraphState Output & Spray Artifacts]

Design & Resilience:
--------------------
Provides a dual-execution architecture with identical operational topology:
1. Direct Native State Machine (`VisionWorkflowRunner`):
   Executes the exact DAG without external framework dependencies, ensuring
   rock-solid local testing, zero-dependency CI runs, and lightweight edge deployment.
2. LangGraph StateGraph Compilation (`create_langgraph_workflow()`):
   When `langgraph` is installed, compiles the identical nodes, cyclic refinement recursion,
   and System 2 deliberative reasoning node into an official LangGraph executable graph.
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
from src.agents.router_contract import BaseRouter
from src.agents.laya_router import LayaTriageRouter

logger = logging.getLogger("agriagent.workflow")


class VisionWorkflowRunner:
    """
    Production orchestrator for AgriAgent System-1 visual reasoning.
    
    Coordinates zero-shot detection, instance segmentation, closed-loop
    error-centroid refinement, triage arbitration, and herbicide savings calculation.
    """

    def __init__(
        self,
        detector: Optional[GroundingDINOEngine] = None,
        segmenter: Optional[SAM2Segmenter] = None,
        laya_router: Optional[Union[LayaTriageRouter, BaseRouter]] = None,
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
        """Node 3: Active closed-loop refinement via morphological error centroid point prompting."""
        img = state.get("image") or state.get("image_path")
        masks = state.get("masks", [])
        state["refinement_count"] = state.get("refinement_count", 0) + 1
        refinement_count = state["refinement_count"]

        if refinement_count > self.max_refinements:
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

            if needs_refine and refinement_count <= self.max_refinements:
                # Calculate morphological error centroid
                box_coords = (box["x1"], box["y1"], box["x2"], box["y2"])
                pt = get_refinement_point(
                    mask_dict["mask_array"],
                    box_coords,
                    predicted_iou=current_iou,
                    threshold=self.iou_threshold,
                    image=img,
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

        return {"masks": updated_masks, "refinement_count": refinement_count}

    def spray_map_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 4: Compute composite spray prescription, weed coverage %, and herbicide savings %."""
        masks = state.get("masks", [])
        img = state.get("image")

        if isinstance(img, Image.Image):
            h, w = img.size[1], img.size[0]
        else:
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

    def triage_node(self, state: GraphState) -> Dict[str, Any]:
        """
        Node 5: System-1 vs System-2 Triage Arbitration.
        Evaluates whether detected foliage warrants escalation to deliberative System 2 reasoning.
        """
        boxes = state.get("boxes", [])
        masks = state.get("masks", [])

        for b, m in zip(boxes, masks):
            escalate, reason = self.laya_router.evaluate_system2_escalation(
                b.get("score", 1.0),
                b.get("label", "weed"),
                m.get("predicted_iou", 1.0),
            )
            if escalate:
                logger.info("VisionWorkflow: Triage escalated to System 2 (%s)", reason)
                return {
                    "system2_needed": True,
                    "vlm_reasoning": f"Laya Triage Alert: {reason}",
                }

        return {"system2_needed": False}

    def system2_node(self, state: GraphState) -> Dict[str, Any]:
        """
        Node 6: Deliberative System 2 Agronomic Reasoner.
        Executes multimodal diagnosis and ICAR/CIBRC RAG prescription when escalated.
        """
        if state.get("system2_needed") and self.system2 is not None:
            logger.info("VisionWorkflow: Executing deliberative System 2 reasoning node.")
            return self.system2.system2_node(state)
        return {}

    def run(self, initial_state: GraphState) -> GraphState:
        """
        Execute the complete reflex state machine sequentially.
        
        Topology matches create_langgraph_workflow() exactly:
        Detect -> Segment -> Refine (cyclic recursion) -> Spray Map -> Triage -> System 2 (conditional).
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

        # 3. Closed-Loop Refinement (cyclic conditional loop)
        for _ in range(self.max_refinements):
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

        # 5. Triage Arbitration
        triage_out = self.triage_node(state)
        state.update(triage_out)

        # 6. Deliberative System 2 Execution (conditional)
        if state.get("system2_needed"):
            s2_out = self.system2_node(state)
            state.update(s2_out)

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
    
    Topological Invariants:
    1. Cyclic refinement recursion: 'refine' loops back to conditional check
       until max_refinements is reached or all masks satisfy iou_threshold.
    2. 'system2' node included in StateGraph when triage arbitrates escalation.
    3. Exactly mirrors VisionWorkflowRunner.run() execution sequence.
    
    Raises ImportError if langgraph is not installed in the active environment.
    """
    from langgraph.graph import StateGraph, START, END

    wf_runner = runner or VisionWorkflowRunner()
    builder = StateGraph(GraphState)

    builder.add_node("detect", wf_runner.detect_node)
    builder.add_node("segment", wf_runner.segment_node)
    builder.add_node("refine", wf_runner.refine_node)
    builder.add_node("spray_map", wf_runner.spray_map_node)
    builder.add_node("triage", wf_runner.triage_node)
    builder.add_node("system2", wf_runner.system2_node)

    # 1. Entry pipeline: START -> detect -> segment
    builder.add_edge(START, "detect")
    builder.add_edge("detect", "segment")

    # 2. Cyclic refinement routing edge
    def should_refine_edge(state: GraphState) -> str:
        count = state.get("refinement_count", 0)
        if count >= wf_runner.max_refinements:
            return "spray_map"
        for m in state.get("masks", []):
            if m.get("predicted_iou", 1.0) < wf_runner.iou_threshold:
                return "refine"
        return "spray_map"

    # From 'segment', conditionally enter 'refine' or skip to 'spray_map'
    builder.add_conditional_edges(
        "segment",
        should_refine_edge,
        {"refine": "refine", "spray_map": "spray_map"}
    )

    # From 'refine', CYCLIC RECURSION back to condition (loops back to 'refine' or exits to 'spray_map')
    builder.add_conditional_edges(
        "refine",
        should_refine_edge,
        {"refine": "refine", "spray_map": "spray_map"}
    )

    # 3. Spray map -> Triage
    builder.add_edge("spray_map", "triage")

    # 4. Triage -> System 2 conditional routing edge
    def should_escalate_edge(state: GraphState) -> str:
        if state.get("system2_needed"):
            return "system2"
        return END

    builder.add_conditional_edges(
        "triage",
        should_escalate_edge,
        {"system2": "system2", END: END}
    )

    # 5. System 2 -> END
    builder.add_edge("system2", END)

    return builder.compile()
