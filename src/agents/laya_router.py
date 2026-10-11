"""
src/agents/laya_router.py
Official Laya System-1 Triage & Fast Decision Engine for AgriAgent.

Architecture Rationale:
-----------------------
AgriAgent is a dual-brain multi-agent system. Traditional AI frameworks use slow,
generative LLMs (taking 3-8 seconds) for every intermediate routing decision.
AgriAgent uses Laya (ConvAI Innovations, Apache 2.0) — a non-autoregressive decision
engine that operates in a single forward pass (<40 ms) without token-by-token generation.

This implementation adheres to the unified BaseRouter contract defined in
src/agents/router_contract.py while maintaining full backward compatibility.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from src.agents.router_contract import (
    BaseRouter,
    RouterAction,
    RouterBackend,
    RouterDecision,
)

logger = logging.getLogger("agriagent.laya")


class LayaTriageRouter(BaseRouter):
    """
    Production wrapper around the official ConvAI Innovations `laya` library,
    implementing the BaseRouter contract.
    
    Attributes:
        preload (bool): Preloads all decision checkpoints for <40 ms latency.
        model_variant (str): 'english' or 'multilingual' (for regional Indian languages).
        fallback_mode (bool): Active when `laya` package is not installed.
    """

    def __init__(self, preload: bool = False, model_variant: str = "english"):
        self.preload = preload
        self.model_variant = model_variant
        self._router = None
        self.fallback_mode = False

        self._initialize_laya()

    @property
    def backend(self) -> RouterBackend:
        return RouterBackend.LAYA

    def _initialize_laya(self) -> None:
        """Safely initialize the official Laya Router."""
        try:
            from laya import Router

            logger.info("Initializing official Laya Router (variant: %s)...", self.model_variant)
            self._router = Router(preload=self.preload)
            logger.info("Laya System-1 Decision Engine initialized successfully.")
        except ImportError:
            logger.warning("Package 'laya' not installed. Using native deterministic System-1 triage fallback.")
            self.fallback_mode = True
        except Exception as e:
            logger.warning("Failed to initialize Laya Router (%s). Using fallback triage.", e)
            self.fallback_mode = True

    def route(
        self,
        detection_confidence: float,
        predicted_iou: float,
        area_pixels: int = 0,
        species_ambiguity: bool = False,
        image_crop: Optional[Any] = None,
        infestation_pct: Optional[float] = None,
        max_allowed_infestation: float = 85.0,
        iou_threshold: float = 0.85,
        min_confidence: float = 0.70,
        label: str = "weed",
        **kwargs: Any,
    ) -> RouterDecision:
        """
        Evaluate perception state via Laya non-autoregressive triage engine.
        """
        t0 = time.perf_counter()

        # 1. Spray safety guardrail
        if infestation_pct is not None and not self.verify_spray_safety(
            infestation_pct=infestation_pct,
            max_allowed_infestation=max_allowed_infestation,
        ):
            latency = (time.perf_counter() - t0) * 1000.0
            return RouterDecision(
                action=RouterAction.SUPPRESS_SPRAY,
                reason=f"Infestation {infestation_pct:.1f}% exceeds threshold ({max_allowed_infestation:.1f}%). Spray suppressed.",
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=1.0,
                probabilities={RouterAction.SUPPRESS_SPRAY.value: 1.0},
                metadata={"infestation_pct": infestation_pct},
            )

        # 2. Refinement evaluation
        needs_refine = self.evaluate_mask_refinement(
            predicted_iou=predicted_iou,
            area_pixels=area_pixels,
            label=label,
            threshold=iou_threshold,
        )
        if needs_refine:
            latency = (time.perf_counter() - t0) * 1000.0
            return RouterDecision(
                action=RouterAction.REFINE,
                reason=f"Mask IoU {predicted_iou:.2f} < threshold {iou_threshold:.2f}. Requires active refinement.",
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=0.92,
                probabilities={RouterAction.REFINE.value: 0.92, RouterAction.ACCEPT.value: 0.08},
                metadata={"predicted_iou": predicted_iou, "iou_threshold": iou_threshold},
            )

        # 3. Species ambiguity check
        if species_ambiguity:
            latency = (time.perf_counter() - t0) * 1000.0
            return RouterDecision(
                action=RouterAction.ESCALATE_SYSTEM2,
                reason=f"Botanical ambiguity detected for species '{label}'. Escalated to System-2 VLM.",
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=0.95,
                probabilities={RouterAction.ESCALATE_SYSTEM2.value: 0.95, RouterAction.ACCEPT.value: 0.05},
                metadata={"species_ambiguity": True, "label": label},
            )

        # 4. System 2 escalation evaluation
        escalate, reason = self.evaluate_system2_escalation(
            detection_confidence=detection_confidence,
            label=label,
            predicted_iou=predicted_iou,
            min_confidence=min_confidence,
        )
        latency = (time.perf_counter() - t0) * 1000.0

        if escalate:
            return RouterDecision(
                action=RouterAction.ESCALATE_SYSTEM2,
                reason=reason,
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=0.88,
                probabilities={RouterAction.ESCALATE_SYSTEM2.value: 0.88, RouterAction.ACCEPT.value: 0.12},
                metadata={"detection_confidence": detection_confidence, "predicted_iou": predicted_iou},
            )

        return RouterDecision(
            action=RouterAction.ACCEPT,
            reason="High confidence detection. System-1 reflex approved for direct spot-spraying.",
            latency_ms=round(latency, 4),
            backend=self.backend,
            confidence=0.96,
            probabilities={RouterAction.ACCEPT.value: 0.96, RouterAction.ESCALATE_SYSTEM2.value: 0.04},
            metadata={"detection_confidence": detection_confidence, "predicted_iou": predicted_iou},
        )

    def evaluate_mask_refinement(
        self,
        predicted_iou: float,
        area_pixels: int,
        label: str = "weed",
        threshold: float = 0.85,
    ) -> bool:
        """
        System-1 decision: Does this instance mask need active geometric refinement?
        
        Uses Laya non-autoregressive triage to evaluate mask quality against rubric.
        """
        if self.fallback_mode or self._router is None:
            # Deterministic mathematical boundary check
            return predicted_iou < threshold

        # Official Laya Router evaluation
        state = f"Target: {label}, Predicted IoU: {predicted_iou:.3f}, Mask Area: {area_pixels} px, Quality Threshold: {threshold}"
        questions = ["Does this segmentation mask fail the quality threshold and require geometric point refinement?"]

        try:
            result = self._router.predict(state, questions)
            # Laya returns calibrated probabilities or boolean answers
            if isinstance(result, dict) and "answers" in result:
                ans = result["answers"][0]
                return str(ans).strip().lower() in ("yes", "true", "1")
            return predicted_iou < threshold
        except Exception as err:
            logger.debug("Laya prediction error: %s. Using heuristic fallback.", err)
            return predicted_iou < threshold

    def evaluate_system2_escalation(
        self,
        detection_confidence: float,
        label: str = "weed",
        predicted_iou: float = 1.0,
        min_confidence: float = 0.70,
    ) -> Tuple[bool, str]:
        """
        System-1 Triage Gate: Determines whether to execute Fast Reflex actuation (<40 ms)
        or Escalate to System-2 Deliberative Reasoning (>1.5 s).
        
        Returns:
            (should_escalate: bool, reason: str)
        """
        # If confidence is high and mask is clean, stay in fast System-1 reflex!
        if detection_confidence >= min_confidence and predicted_iou >= 0.80:
            return (False, "High confidence detection. System-1 reflex approved for direct spot-spraying.")

        if self.fallback_mode or self._router is None:
            if detection_confidence < min_confidence:
                return (True, f"Low detection confidence ({detection_confidence:.2f} < {min_confidence}). Escalating to VLM critic.")
            return (True, f"Sub-optimal mask quality (IoU {predicted_iou:.2f}). Escalating to agronomy advisor.")

        # Official Laya Router evaluation
        state = (
            f"Species: {label}, Detection Score: {detection_confidence:.2f}, "
            f"Mask Fidelity IoU: {predicted_iou:.2f}. Min Required: {min_confidence}."
        )
        questions = [
            "Is the confidence too low or the botanical symptom too ambiguous for automated robotic spraying?",
        ]

        try:
            result = self._router.predict(state, questions)
            ans = str(result.get("answers", ["yes"])[0]).lower()
            should_escalate = ans in ("yes", "true", "1")
            reason = "Laya triage flagged ambiguous foliage for Multimodal VLM inspection." if should_escalate else "System-1 validated."
            return (should_escalate, reason)
        except Exception:
            return (detection_confidence < min_confidence, "Confidence heuristic triage.")

    def verify_spray_safety(
        self,
        infestation_pct: float,
        buffer_pixels: int = 10,
        max_allowed_infestation: float = 85.0,
    ) -> bool:
        """
        Safety Guardrail: Ensures spot-spraying is physically and agronomically viable.
        If infestation exceeds 85%, spot-spraying is abandoned in favor of emergency broadcast alert.
        """
        return infestation_pct <= max_allowed_infestation
