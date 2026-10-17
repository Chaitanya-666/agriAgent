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
from typing import Any, Dict, List, Optional, Tuple, cast
import numpy as np
from PIL import Image

from src.state import Artifact, ArtifactType, Box, GraphState, Mask
from src.vision.grounding_dino import GroundingDINOEngine
from src.vision.sam2_wrapper import SAM2Segmenter
from src.vision.refinement import get_refinement_point
from src.evaluation.iou_dice import compute_herbicide_savings
from src.agents.router_contract import BaseRouter
from src.agents.router_contract import RouterAction
from src.agents.deterministic_router import DeterministicRouter
from src.agents.clef_flash_router import ClefFlashRouter

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
        router: Optional[BaseRouter] = None,
        iou_threshold: float = 0.85,
        max_refinements: int = 2,
        buffer_pixels: int = 10,
        mock_mode: bool = False,
        system2: Optional[Any] = None,
    ):
        self.mock_mode = mock_mode
        self.detector = detector or GroundingDINOEngine(mock_mode=mock_mode)
        self.segmenter = segmenter or SAM2Segmenter(mock_mode=mock_mode)
        self.safety_router = DeterministicRouter()
        self.router = router or ClefFlashRouter(mock_mode=mock_mode)
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

        prompt = state.get("text_prompt") or "weed . grass . pigweed ."
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
        if img is None:
            logger.warning("VisionWorkflow: Cannot segment boxes without an input image.")
            return {"masks": [], "error": "Cannot segment without an input image."}

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
        if img is None:
            logger.warning("VisionWorkflow: Cannot refine masks without an input image.")
            return {"masks": masks, "refinement_count": refinement_count}

        updated_masks: List[Mask] = []
        refined_any = False

        for mask_dict in masks:
            current_iou = mask_dict.get("predicted_iou", 1.0)
            box = mask_dict["box"]
            area_px = int(mask_dict["mask_array"].sum())
            label = box.get("label", "weed")

            needs_refine = self.safety_router.evaluate_mask_refinement(
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
                    image=img if isinstance(img, (Image.Image, np.ndarray)) else None,
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
        # Strict explicit exclusion set for cash crops
        disallowed_crop_labels = {
            "crop",
            "cotton",
            "sugarbeet",
            "sugar_beet",
            "beet",
            "cash_crop",
            "plant",
            "broadleaf_plant",
            "cultivated",
            "soil",
            "background",
        }
        crop_name_tokens = ("cotton", "sugarbeet", "sugar_beet", "beet", "crop")
        # Recognized weed keywords
        recognized_weed_keywords = (
            "weed",
            "invasive",
            "target",
            "grass",
            "pigweed",
            "carpetweed",
            "velvetleaf",
        )
        contributing_weeds = 0
        approved_zones: List[Dict[str, Any]] = []

        for m in masks:
            raw_label = m.get("label")
            if raw_label is None:
                continue
            normalized_label = str(raw_label).strip().lower().replace("-", "_")

            # Explicit fail-closed policy: never spray any label in disallowed crops or containing crop
            is_disallowed = normalized_label in disallowed_crop_labels or any(
                token in normalized_label for token in crop_name_tokens
            )

            is_recognized_weed = not is_disallowed and any(
                kw in normalized_label for kw in recognized_weed_keywords
            )

            if is_recognized_weed:
                approved_mask = np.asarray(m["mask_array"], dtype=bool)
                composite_mask |= approved_mask
                contributing_weeds += 1
                ys, xs = np.where(approved_mask)
                if len(xs):
                    approved_zones.append(
                        {
                            "label": normalized_label,
                            "score": float(m["box"].get("score", 0.9)),
                            "bbox": [
                                int(xs.min()),
                                int(ys.min()),
                                int(xs.max()) + 1,
                                int(ys.max()) + 1,
                            ],
                            "mask": approved_mask.astype(np.uint8),
                        }
                    )
            else:
                logger.debug(
                    "VisionWorkflow: Skipping non-weed mask (label: %s) from spray map.",
                    raw_label,
                )

        weed_pixel_count = int(composite_mask.sum())
        total_pixels = h * w
        infestation_pct = round((weed_pixel_count / total_pixels) * 100.0, 2)

        safety_decision = DeterministicRouter().route(
            detection_confidence=1.0,
            predicted_iou=1.0,
            infestation_pct=infestation_pct,
            max_allowed_infestation=85.0,
        )
        spray_allowed = safety_decision.action != RouterAction.SUPPRESS_SPRAY
        if not spray_allowed:
            composite_mask[:] = False
            approved_zones = []

        chemical_savings_pct = compute_herbicide_savings(
            composite_mask, (h, w), buffer_pixels=self.buffer_pixels
        )

        spray_map_data = {
            "infestation_percentage": infestation_pct,
            "chemical_savings_percentage": round(chemical_savings_pct, 2),
            "weed_count": contributing_weeds,
            "total_masks_evaluated": len(masks),
            "buffer_pixels": self.buffer_pixels,
            "target_resolution": {"width": w, "height": h},
            "spray_allowed": spray_allowed,
            "safety_action": safety_decision.action.value,
            "status": (
                "Selective Spot-Spray Prescription Generated"
                if spray_allowed
                else "SUPPRESS_SPRAY: infestation exceeds safety ceiling"
            ),
        }

        # Build serializable artifact
        spray_artifact = Artifact(
            id="spray_prescription_01",
            type=ArtifactType.SPRAY_MAP,
            title="Precision Herbicide Spray Map",
            description=f"Generated prescription saving {chemical_savings_pct:.1f}% chemical volume.",
            metadata=spray_map_data,
            payload={"composite_mask": composite_mask, "approved_spray_zones": approved_zones},
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
        image = state.get("image")

        for b, m in zip(boxes, masks):
            label = str(b.get("label", "weed")).strip().lower().replace("-", "_")
            normalized = label.replace(" ", "_")
            known_weeds = ("weed", "grass", "pigweed", "carpetweed", "velvetleaf", "invasive")
            crop_terms = ("cotton", "sugarbeet", "sugar_beet", "beet", "crop")
            species_ambiguity = "ambig" in normalized or not any(
                term in normalized for term in known_weeds + crop_terms
            )
            confidence = float(b.get("score", 1.0))
            predicted_iou = float(m.get("predicted_iou", 1.0))
            deterministic_decision = self.safety_router.route(
                detection_confidence=confidence,
                predicted_iou=predicted_iou,
                label=label,
            )
            if deterministic_decision.action == RouterAction.ESCALATE_SYSTEM2 or confidence < 0.70:
                logger.info(
                    "VisionWorkflow: Deterministic triage escalated to System 2 (%s)",
                    deterministic_decision.reason,
                )
                return {
                    "system2_needed": True,
                    "vlm_reasoning": f"Deterministic triage: {deterministic_decision.reason}",
                }
            if species_ambiguity:
                image_crop = None
                if isinstance(image, Image.Image):
                    x1 = max(0, int(b.get("x1", 0)))
                    y1 = max(0, int(b.get("y1", 0)))
                    x2 = min(image.width, int(b.get("x2", image.width)))
                    y2 = min(image.height, int(b.get("y2", image.height)))
                    if x2 > x1 and y2 > y1:
                        image_crop = image.crop((x1, y1, x2, y2))
                decision = self.router.route(
                    detection_confidence=confidence,
                    predicted_iou=predicted_iou,
                    label=label,
                    species_ambiguity=True,
                    image_crop=image_crop,
                )
                if decision.action == RouterAction.ESCALATE_SYSTEM2:
                    logger.info(
                        "VisionWorkflow: Local triage escalated to System 2 (%s)", decision.reason
                    )
                    return {"system2_needed": True, "vlm_reasoning": decision.reason}

        return {"system2_needed": False}

    def system2_node(self, state: GraphState) -> Dict[str, Any]:
        """
        Node 6: Deliberative System 2 Agronomic Reasoner.
        Executes multimodal diagnosis and ICAR/CIBRC RAG prescription when escalated.
        """
        if state.get("system2_needed") and self.system2 is not None:
            logger.info("VisionWorkflow: Executing deliberative System 2 reasoning node.")
            try:
                return self.system2.system2_node(state)
            except Exception as exc:
                # A failed reasoning call must not discard the vision results; record why
                # no diagnosis or prescription exists instead of crashing the run.
                logger.error("VisionWorkflow: System 2 failed: %s", exc)
                return {"system2_error": str(exc), "prescription_report": None}
        return {}

    def run(self, initial_state: GraphState) -> GraphState:
        """
        Execute the complete reflex state machine sequentially.

        Topology matches create_langgraph_workflow() exactly:
        Detect -> Segment -> Refine (cyclic recursion) -> Spray Map -> Triage -> System 2 (conditional).
        """
        state = initial_state.copy()

        def merge_node_output(output: Dict[str, Any]) -> None:
            # Node methods are dynamic graph boundaries; runtime state remains a GraphState.
            state.update(cast(Any, output))

        state.setdefault("refinement_count", 0)
        state.setdefault("artifacts", {})
        state.setdefault("messages", [])

        # 1. Detection
        det_out = self.detect_node(state)
        merge_node_output(det_out)
        if state.get("error"):
            return state

        # 2. Segmentation
        seg_out = self.segment_node(state)
        merge_node_output(seg_out)

        # 3. Closed-Loop Refinement (cyclic conditional loop)
        for _ in range(self.max_refinements):
            needs_refine = any(
                m.get("predicted_iou", 1.0) < self.iou_threshold for m in state.get("masks", [])
            )
            if not needs_refine:
                break
            ref_out = self.refine_node(state)
            merge_node_output(ref_out)

        # 4. Spray Map Generation
        spray_out = self.spray_map_node(state)
        merge_node_output(spray_out)

        # 5. Triage Arbitration
        triage_out = self.triage_node(state)
        merge_node_output(triage_out)

        # 6. Deliberative System 2 Execution (conditional)
        if state.get("system2_needed"):
            s2_out = self.system2_node(state)
            merge_node_output(s2_out)

        return state


def create_initial_state(
    image: Image.Image,
    text_prompt: str = "weed . grass . pigweed .",
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
        "system2_error": None,
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
        "segment", should_refine_edge, {"refine": "refine", "spray_map": "spray_map"}
    )

    # From 'refine', CYCLIC RECURSION back to condition (loops back to 'refine' or exits to 'spray_map')
    builder.add_conditional_edges(
        "refine", should_refine_edge, {"refine": "refine", "spray_map": "spray_map"}
    )

    # 3. Spray map -> Triage
    builder.add_edge("spray_map", "triage")

    # 4. Triage -> System 2 conditional routing edge
    def should_escalate_edge(state: GraphState) -> str:
        if state.get("system2_needed"):
            return "system2"
        return END

    builder.add_conditional_edges("triage", should_escalate_edge, {"system2": "system2", END: END})

    # 5. System 2 -> END
    builder.add_edge("system2", END)

    return builder.compile()
