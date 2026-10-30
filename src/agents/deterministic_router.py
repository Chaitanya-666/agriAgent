"""
src/agents/deterministic_router.py
Sub-millisecond System-1 Fast Reflex Deterministic Router for AgriAgent.

Architecture Rationale:
-----------------------
Autonomous field spot-sprayers operating at 10-20 km/h require hard real-time
latencies (<40 ms) and cannot tolerate cloud network dropouts in rural fields.
This deterministic router evaluates boolean and floating-point inequality rules
in sub-millisecond time (<0.05 ms) with zero network dependency, zero hallucination
risk, and zero operational cost.
"""

import time
from typing import Any, Dict, Optional, Tuple
import numpy as np

from src.agents.router_contract import (
    BaseRouter,
    RouterAction,
    RouterBackend,
    RouterDecision,
)


class DeterministicRouter(BaseRouter):
    """
    Hard real-time deterministic triage router for System-1 reflexes.
    """

    @property
    def backend(self) -> RouterBackend:
        return RouterBackend.DETERMINISTIC

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
        Evaluate perception state against deterministic agricultural guardrails.
        """
        t0 = time.perf_counter()

        # 1. Statutory spray safety guardrail: excessive weed infestation
        if infestation_pct is not None and float(infestation_pct) > float(max_allowed_infestation):
            latency = (time.perf_counter() - t0) * 1000.0
            return RouterDecision(
                action=RouterAction.SUPPRESS_SPRAY,
                reason=(
                    f"Infestation {infestation_pct:.1f}% exceeds statutory safety ceiling "
                    f"({max_allowed_infestation:.1f}%). Spot-spraying suppressed in favor of broadcast protocol."
                ),
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=1.0,
                probabilities={
                    RouterAction.SUPPRESS_SPRAY.value: 1.0,
                    RouterAction.ACCEPT.value: 0.0,
                    RouterAction.REFINE.value: 0.0,
                    RouterAction.ESCALATE_SYSTEM2.value: 0.0,
                },
                metadata={"infestation_pct": infestation_pct, "rule": "safety_ceiling_breached"},
            )

        # 2. Geometric mask refinement check: IoU below active threshold
        if float(predicted_iou) < float(iou_threshold):
            latency = (time.perf_counter() - t0) * 1000.0
            return RouterDecision(
                action=RouterAction.REFINE,
                reason=f"Mask IoU ({predicted_iou:.2f}) falls below quality threshold ({iou_threshold:.2f}). Requires geometric point refinement.",
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=1.0,
                probabilities={
                    RouterAction.REFINE.value: 1.0,
                    RouterAction.ACCEPT.value: 0.0,
                    RouterAction.ESCALATE_SYSTEM2.value: 0.0,
                    RouterAction.SUPPRESS_SPRAY.value: 0.0,
                },
                metadata={"predicted_iou": predicted_iou, "iou_threshold": iou_threshold},
            )

        # 3. System-2 Deliberative Escalation checks
        if species_ambiguity:
            latency = (time.perf_counter() - t0) * 1000.0
            return RouterDecision(
                action=RouterAction.ESCALATE_SYSTEM2,
                reason=f"Species ambiguity flagged for '{label}'. Escalating to multimodal VLM agronomic reasoner.",
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=1.0,
                probabilities={
                    RouterAction.ESCALATE_SYSTEM2.value: 1.0,
                    RouterAction.ACCEPT.value: 0.0,
                    RouterAction.REFINE.value: 0.0,
                    RouterAction.SUPPRESS_SPRAY.value: 0.0,
                },
                metadata={"species_ambiguity": True, "label": label},
            )

        if float(detection_confidence) < float(min_confidence):
            latency = (time.perf_counter() - t0) * 1000.0
            return RouterDecision(
                action=RouterAction.ESCALATE_SYSTEM2,
                reason=f"Low detection confidence ({detection_confidence:.2f} < {min_confidence:.2f}). Withheld for review.",
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=1.0,
                probabilities={
                    RouterAction.ESCALATE_SYSTEM2.value: 1.0,
                    RouterAction.ACCEPT.value: 0.0,
                    RouterAction.REFINE.value: 0.0,
                    RouterAction.SUPPRESS_SPRAY.value: 0.0,
                },
                metadata={"detection_confidence": detection_confidence, "min_confidence": min_confidence},
            )

        if float(predicted_iou) < 0.80:
            latency = (time.perf_counter() - t0) * 1000.0
            return RouterDecision(
                action=RouterAction.ESCALATE_SYSTEM2,
                reason=f"Sub-optimal mask quality (IoU {predicted_iou:.2f} < 0.80). Escalating to agronomy advisor.",
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=1.0,
                probabilities={
                    RouterAction.ESCALATE_SYSTEM2.value: 1.0,
                    RouterAction.ACCEPT.value: 0.0,
                    RouterAction.REFINE.value: 0.0,
                    RouterAction.SUPPRESS_SPRAY.value: 0.0,
                },
                metadata={"predicted_iou": predicted_iou},
            )

        # 4. Standard fast reflex approval
        latency = (time.perf_counter() - t0) * 1000.0
        return RouterDecision(
            action=RouterAction.ACCEPT,
            reason="High confidence detection and clean mask. Approved for System-1 spot-spraying.",
            latency_ms=round(latency, 4),
            backend=self.backend,
            confidence=1.0,
            probabilities={
                RouterAction.ACCEPT.value: 1.0,
                RouterAction.REFINE.value: 0.0,
                RouterAction.ESCALATE_SYSTEM2.value: 0.0,
                RouterAction.SUPPRESS_SPRAY.value: 0.0,
            },
            metadata={"detection_confidence": detection_confidence, "predicted_iou": predicted_iou},
        )

    def evaluate_mask_refinement(
        self,
        predicted_iou: float,
        area_pixels: int = 0,
        label: str = "weed",
        threshold: float = 0.85,
    ) -> bool:
        """Fast reflex path: sub-microsecond inequality check."""
        return float(predicted_iou) < float(threshold)

    def evaluate_system2_escalation(
        self,
        detection_confidence: float,
        label: str = "weed",
        predicted_iou: float = 1.0,
        min_confidence: float = 0.70,
    ) -> Tuple[bool, str]:
        """Fast reflex path for System 2 triage."""
        if float(detection_confidence) >= float(min_confidence) and float(predicted_iou) >= 0.80:
            return (False, "High confidence detection. System-1 reflex approved for direct spot-spraying.")
        if float(detection_confidence) < float(min_confidence):
            return (True, f"Low detection confidence ({detection_confidence:.2f} < {min_confidence:.2f}). Withheld for review.")
        return (True, f"Sub-optimal mask quality (IoU {predicted_iou:.2f}). Escalating to agronomy advisor.")

    def verify_spray_safety(
        self,
        infestation_pct: float,
        buffer_pixels: int = 10,
        max_allowed_infestation: float = 85.0,
    ) -> bool:
        """Fast reflex path for spray safety guardrail."""
        return float(infestation_pct) <= float(max_allowed_infestation)
