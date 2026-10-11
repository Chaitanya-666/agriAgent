"""
src/agents/router_contract.py
Standardized Triage & Routing Interface Contract for AgriAgent.

Defines the core contracts, data models, and abstract base classes for System-1
fast triage and System-2 escalation across different decision backends:
- DETERMINISTIC: Rules that remain the final spray safety authority.
- CLEF_FLASH: Local Cloudflare/Clef Flash model used only for triage.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field


class RouterAction(str, Enum):
    """Discrete actuation and routing decisions available to AgriAgent."""
    ACCEPT = "ACCEPT"                    # Clean detection & mask; approved for robotic spot-spray.
    REFINE = "REFINE"                    # Mask quality below threshold; requires active point refinement.
    ESCALATE_SYSTEM2 = "ESCALATE_SYSTEM2" # Ambiguous species / low confidence; escalate to VLM/RAG advisor.
    SUPPRESS_SPRAY = "SUPPRESS_SPRAY"    # Safety guardrail violation (e.g. saturation); abort spot spray.


class RouterBackend(str, Enum):
    """Supported local triage routing engines."""
    DETERMINISTIC = "deterministic"
    CLEF_FLASH = "clef_flash"


class RouterDecision(BaseModel):
    """
    Standardized routing decision returned by all AgriAgent routers.
    """
    action: RouterAction = Field(..., description="Selected routing action")
    reason: str = Field(..., description="Human and machine-readable explanation of the decision")
    latency_ms: float = Field(..., description="Wall-clock decision latency in milliseconds")
    backend: RouterBackend = Field(..., description="Engine backend that produced this decision")
    confidence: float = Field(default=1.0, description="Calibrated confidence or probability of the decision [0.0, 1.0]")
    probabilities: Dict[str, float] = Field(default_factory=dict, description="Distribution across all candidate actions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Engine-specific telemetry and debug information")


class BaseRouter(ABC):
    """
    Abstract Base Class for all AgriAgent routing engines.
    
    Guarantees a unified contract across deterministic and local Clef triage.
    """

    @property
    @abstractmethod
    def backend(self) -> RouterBackend:
        """Returns the identifier of the router backend."""
        pass

    @abstractmethod
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
        Evaluate perception state and return a standardized RouterDecision.
        """
        pass

    def evaluate_mask_refinement(
        self,
        predicted_iou: float,
        area_pixels: int,
        label: str = "weed",
        threshold: float = 0.85,
    ) -> bool:
        """
        Helper interface: Evaluates whether instance mask requires geometric refinement.
        """
        decision = self.route(
            detection_confidence=1.0,
            predicted_iou=predicted_iou,
            area_pixels=area_pixels,
            iou_threshold=threshold,
            label=label,
        )
        return decision.action == RouterAction.REFINE

    def evaluate_system2_escalation(
        self,
        detection_confidence: float,
        label: str = "weed",
        predicted_iou: float = 1.0,
        min_confidence: float = 0.70,
    ) -> Tuple[bool, str]:
        """
        Helper interface: Evaluates whether detection warrants System 2 escalation.
        Returns: (should_escalate, reason)
        """
        decision = self.route(
            detection_confidence=detection_confidence,
            predicted_iou=predicted_iou,
            min_confidence=min_confidence,
            label=label,
        )
        should_escalate = (decision.action == RouterAction.ESCALATE_SYSTEM2)
        return (should_escalate, decision.reason)

    def verify_spray_safety(
        self,
        infestation_pct: float,
        buffer_pixels: int = 10,
        max_allowed_infestation: float = 85.0,
    ) -> bool:
        """
        Safety Guardrail: Ensures spot-spraying is physically and agronomically viable.
        Returns False (suppress) if infestation exceeds threshold.
        """
        decision = self.route(
            detection_confidence=1.0,
            predicted_iou=1.0,
            infestation_pct=infestation_pct,
            max_allowed_infestation=max_allowed_infestation,
        )
        return decision.action != RouterAction.SUPPRESS_SPRAY
