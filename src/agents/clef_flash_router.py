"""Local Clef Flash triage adapter.

This module never contacts Cloudflare. Clef may recommend escalation, but a
DeterministicRouter remains the authority for every spray safety decision.
"""

import importlib
import logging
import os
import sys
import time
from typing import Any, Dict, Optional

from src.agents.deterministic_router import DeterministicRouter
from src.agents.router_contract import (
    BaseRouter,
    RouterAction,
    RouterBackend,
    RouterDecision,
)

logger = logging.getLogger("agriagent.clef_flash")
DEFAULT_MODEL = "Cloudflare/clef-flash"


class ClefFlashRouter(BaseRouter):
    """Use local Clef Flash for ambiguity triage, with explicit mock mode."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        mock_mode: bool = False,
    ) -> None:
        self.model_name = model_name or os.environ.get("CLEF_FLASH_MODEL", DEFAULT_MODEL)
        self.mock_mode = mock_mode
        self._model: Any = None
        self._processor: Any = None
        self._model_module: Any = None
        self.safety_router = DeterministicRouter()

    @property
    def backend(self) -> RouterBackend:
        return RouterBackend.CLEF_FLASH

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise RuntimeError(
                "Local Clef Flash needs torch, transformers, and huggingface_hub. Install the local-model "
                "extras and follow docs/models_and_runtime.md. No cloud or mock fallback is enabled."
            ) from exc
        try:
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "Clef Flash GPU runtime is unavailable. Its published local example was tested "
                    "on an H200; CPU inference has not been validated for this project."
                )
            snapshot_path = snapshot_download(
                repo_id=self.model_name,
                revision=os.environ.get("CLEF_FLASH_REVISION") or None,
                local_files_only=True,
            )
            if snapshot_path not in sys.path:
                sys.path.insert(0, snapshot_path)
            self._model_module = importlib.import_module("joint_schema_model")
            device = torch.device("cuda")
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            self._model, self._processor = self._model_module.load_release_model(
                snapshot_path, device=device, dtype=dtype
            )
        except Exception as exc:
            self._processor = None
            self._model_module = None
            self._model = None
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(
                f"Local Clef Flash model '{self.model_name}' is unavailable or could not be "
                "loaded. Download the weights and verify hardware/runtime setup."
            ) from exc

    def _classify_ambiguity(self, telemetry: Dict[str, Any], image_crop: Any = None) -> bool:
        if self.mock_mode:
            # Mock mode stands in for an ambiguous label only; it cannot approve spraying.
            return bool(telemetry["species_ambiguity"])
        self._load_model()
        assert self._processor is not None and self._model is not None
        assert self._model_module is not None
        record: Dict[str, Any] = {
            "model": self.model_name,
            "state": telemetry,
            "questions": {
                "triage": {
                    "type": "choice",
                    "instructions": "Does this image or telemetry leave the target vegetation identity ambiguous?",
                    "criteria": {
                        "escalate": "The plant identity or target status is uncertain; require System 2 review.",
                        "clear": "The target status is sufficiently clear for downstream deterministic checks.",
                    },
                }
            },
        }
        if image_crop is not None:
            try:
                from PIL import Image
                import numpy as np

                if isinstance(image_crop, np.ndarray):
                    image_crop = Image.fromarray(image_crop.astype("uint8")).convert("RGB")
                elif isinstance(image_crop, Image.Image):
                    image_crop = image_crop.convert("RGB")
                else:
                    raise TypeError("image_crop must be a PIL image or NumPy array")
                record["images"] = [image_crop]
            except ImportError as exc:
                raise RuntimeError("Pillow and NumPy are required for image triage.") from exc
        result = self._model_module.systemone(self._model, self._processor, record)
        choice = result["answers"]["triage"]["choice"]
        return choice != "clear"

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
        """Return deterministic safety/refinement outcomes or local triage advice."""
        started = time.perf_counter()
        safety = self.safety_router.route(
            detection_confidence=detection_confidence,
            predicted_iou=predicted_iou,
            area_pixels=area_pixels,
            species_ambiguity=False,
            infestation_pct=infestation_pct,
            max_allowed_infestation=max_allowed_infestation,
            iou_threshold=iou_threshold,
            min_confidence=min_confidence,
            label=label,
        )
        if safety.action != RouterAction.ACCEPT:
            return safety.model_copy(update={"backend": self.backend})

        telemetry = {
            "detection_confidence": detection_confidence,
            "predicted_iou": predicted_iou,
            "area_pixels": area_pixels,
            "species_ambiguity": species_ambiguity,
            "label": label,
        }
        try:
            escalate = self._classify_ambiguity(telemetry, image_crop=image_crop)
        except Exception as exc:
            logger.exception("Local Clef Flash triage unavailable; escalating safely to System 2.")
            elapsed = (time.perf_counter() - started) * 1000
            return RouterDecision(
                action=RouterAction.ESCALATE_SYSTEM2,
                reason=f"Local Clef Flash unavailable; System 2 review required: {exc}",
                latency_ms=round(elapsed, 4),
                backend=self.backend,
                confidence=0.0,
                probabilities={RouterAction.ESCALATE_SYSTEM2.value: 1.0},
                metadata={"model_name": self.model_name, "mock_mode": False, "runtime_error": str(exc)},
            )
        action = RouterAction.ESCALATE_SYSTEM2 if escalate else RouterAction.ACCEPT
        elapsed = (time.perf_counter() - started) * 1000
        return RouterDecision(
            action=action,
            reason=(
                "Local Clef Flash recommends System 2 review."
                if escalate
                else "Local Clef Flash triage found no additional ambiguity; deterministic safety gate remains authoritative."
            ),
            latency_ms=round(elapsed, 4),
            backend=self.backend,
            confidence=1.0 if self.mock_mode else 0.0,
            probabilities={action.value: 1.0},
            metadata={"model_name": self.model_name, "mock_mode": self.mock_mode},
        )
