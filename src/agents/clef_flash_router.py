"""
src/agents/clef_flash_router.py
Cloudflare Clef Flash (Qwen3.5-9B) Multimodal Decision Router for AgriAgent.

Architecture Rationale:
-----------------------
Cloudflare Clef Flash is a 9-billion parameter decision model based on Qwen3.5-9B,
specialized for high-throughput single-pass classification and routing.
Unlike text-only routers (such as Laya), Clef Flash supports multimodal inputs:
numerical telemetry paired with real field image crops.

This adapter provides:
1. Multimodal payload formatting (visual crops + numeric telemetry).
2. Schema-conforming prompt formulation with candidate action set.
3. Probability output parsing across candidate actions.
4. Fail-safe edge fallback: If cloud requests fail, time out, or lose connectivity,
   execution immediately falls back to local DeterministicRouter (<0.05 ms).
"""

import base64
import io
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from PIL import Image

from src.agents.router_contract import (
    BaseRouter,
    RouterAction,
    RouterBackend,
    RouterDecision,
)
from src.agents.deterministic_router import DeterministicRouter

logger = logging.getLogger("agriagent.clef_flash")


class ClefFlashRouter(BaseRouter):
    """
    Cloudflare Clef Flash (Qwen3.5-9B) Multimodal Decision Router.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        account_id: Optional[str] = None,
        model_name: str = "@cf/meta/clef-flash",
        timeout_seconds: float = 2.0,
        fallback_router: Optional[BaseRouter] = None,
        mock_mode: bool = False,
    ):
        self.api_token = api_token or os.environ.get("CLOUDFLARE_API_TOKEN")
        self.account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.fallback_router = fallback_router or DeterministicRouter()
        self.mock_mode = mock_mode or (not self.api_token and not self.account_id)

    @property
    def backend(self) -> RouterBackend:
        return RouterBackend.CLEF_FLASH

    def _encode_image_crop(self, image_crop: Any) -> Optional[str]:
        """Encodes an image crop into base64 JPEG string for multimodal VLM prompt."""
        if image_crop is None:
            return None
        try:
            if isinstance(image_crop, np.ndarray):
                # Ensure uint8 RGB
                if image_crop.dtype != np.uint8:
                    if image_crop.max() <= 1.0:
                        image_crop = (image_crop * 255).astype(np.uint8)
                    else:
                        image_crop = image_crop.astype(np.uint8)
                if image_crop.ndim == 2:
                    pil_img = Image.fromarray(image_crop)
                elif image_crop.shape[2] == 3:
                    pil_img = Image.fromarray(image_crop, "RGB")
                else:
                    pil_img = Image.fromarray(image_crop[..., :3], "RGB")
            elif isinstance(image_crop, Image.Image):
                pil_img = image_crop.convert("RGB")
            elif isinstance(image_crop, str) and os.path.exists(image_crop):
                pil_img = Image.open(image_crop).convert("RGB")
            elif isinstance(image_crop, str):
                # Assume already base64 string
                return image_crop
            else:
                return None

            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as err:
            logger.debug("Failed to encode image crop for Clef Flash: %s", err)
            return None

    def _execute_mock_inference(
        self,
        detection_confidence: float,
        predicted_iou: float,
        area_pixels: int,
        species_ambiguity: bool,
        has_image: bool,
        infestation_pct: Optional[float],
        max_allowed_infestation: float,
        iou_threshold: float,
        min_confidence: float,
        label: str,
    ) -> Dict[str, Any]:
        """
        Simulates Qwen3.5-9B Clef Flash calibrated decision probabilities.
        """
        # 1. Statutory spray safety check
        if infestation_pct is not None and float(infestation_pct) > float(max_allowed_infestation):
            return {
                "action": RouterAction.SUPPRESS_SPRAY,
                "probabilities": {
                    RouterAction.SUPPRESS_SPRAY.value: 0.98,
                    RouterAction.ACCEPT.value: 0.01,
                    RouterAction.REFINE.value: 0.005,
                    RouterAction.ESCALATE_SYSTEM2.value: 0.005,
                },
                "confidence": 0.98,
                "reason": (
                    f"Clef Flash safety guardrail: Infestation {infestation_pct:.1f}% exceeds "
                    f"ceiling {max_allowed_infestation:.1f}%. Suppressing spot spray."
                ),
            }

        # 2. Geometric refinement check
        if float(predicted_iou) < float(iou_threshold):
            prob = 0.91 if has_image else 0.88
            return {
                "action": RouterAction.REFINE,
                "probabilities": {
                    RouterAction.REFINE.value: prob,
                    RouterAction.ACCEPT.value: round(1.0 - prob - 0.04, 3),
                    RouterAction.ESCALATE_SYSTEM2.value: 0.03,
                    RouterAction.SUPPRESS_SPRAY.value: 0.01,
                },
                "confidence": prob,
                "reason": (
                    f"Clef Flash visual evaluation: Instance mask IoU ({predicted_iou:.2f}) "
                    f"below threshold ({iou_threshold:.2f}). Triggering contour refinement."
                ),
            }

        # 3. Deliberative System 2 escalation
        if species_ambiguity or float(detection_confidence) < float(min_confidence) or float(predicted_iou) < 0.80:
            prob = 0.94 if has_image else 0.89
            reason_details = []
            if species_ambiguity:
                reason_details.append(f"species ambiguity for '{label}'")
            if float(detection_confidence) < float(min_confidence):
                reason_details.append(f"low confidence {detection_confidence:.2f}")
            if float(predicted_iou) < 0.80:
                reason_details.append(f"marginal IoU {predicted_iou:.2f}")

            return {
                "action": RouterAction.ESCALATE_SYSTEM2,
                "probabilities": {
                    RouterAction.ESCALATE_SYSTEM2.value: prob,
                    RouterAction.ACCEPT.value: round(1.0 - prob - 0.02, 3),
                    RouterAction.REFINE.value: 0.015,
                    RouterAction.SUPPRESS_SPRAY.value: 0.005,
                },
                "confidence": prob,
                "reason": f"Clef Flash VLM inspection: Escalating to System 2 due to {', '.join(reason_details)}.",
            }

        # 4. Fast reflex approved
        prob = 0.95
        return {
            "action": RouterAction.ACCEPT,
            "probabilities": {
                RouterAction.ACCEPT.value: prob,
                RouterAction.REFINE.value: 0.02,
                RouterAction.ESCALATE_SYSTEM2.value: 0.02,
                RouterAction.SUPPRESS_SPRAY.value: 0.01,
            },
            "confidence": prob,
            "reason": "Clef Flash multimodal validation confirmed high confidence and clean foliage boundaries.",
        }

    def _execute_cloud_inference(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executes HTTP POST request against Cloudflare Workers AI API endpoint.
        """
        import urllib.request
        import urllib.error

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{self.model_name}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            raw_body = resp.read().decode("utf-8")
            response_json = json.loads(raw_body)
            if not response_json.get("success", False):
                raise RuntimeError(f"Cloudflare API returned error: {response_json.get('errors')}")
            return response_json.get("result", {})

    def _parse_probabilities(
        self,
        raw_result: Dict[str, Any],
    ) -> Tuple[RouterAction, Dict[str, float], float, str]:
        """
        Parses calibrated probability output from Clef Flash response.
        """
        action_str = str(raw_result.get("action", "")).upper().strip()
        probabilities = raw_result.get("probabilities", {})
        reason = str(raw_result.get("reason", "Clef Flash automated decision"))

        # Map to valid RouterAction
        try:
            action = RouterAction(action_str)
        except ValueError:
            # Fallback to action with highest probability if available
            if probabilities:
                best_act = max(probabilities.items(), key=lambda kv: kv[1])[0]
                action = RouterAction(best_act)
            else:
                action = RouterAction.ACCEPT

        # Normalize probability dictionary
        norm_probs: Dict[str, float] = {}
        total = sum(probabilities.values()) if probabilities else 0.0
        for act in RouterAction:
            val = float(probabilities.get(act.value, 0.0))
            norm_probs[act.value] = round(val / total, 4) if total > 0 else (1.0 if act == action else 0.0)

        confidence = norm_probs.get(action.value, float(raw_result.get("confidence", 0.90)))
        return (action, norm_probs, confidence, reason)

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
        Evaluate perception state using Cloudflare Clef Flash with fail-safe local fallback.
        """
        t0 = time.perf_counter()
        encoded_image = self._encode_image_crop(image_crop)
        has_image = (encoded_image is not None)

        telemetry = {
            "detection_confidence": round(float(detection_confidence), 3),
            "predicted_iou": round(float(predicted_iou), 3),
            "area_pixels": int(area_pixels),
            "species_ambiguity": bool(species_ambiguity),
            "infestation_percentage": float(infestation_pct) if infestation_pct is not None else None,
            "label": label,
            "iou_threshold": iou_threshold,
            "min_confidence": min_confidence,
        }

        try:
            if self.mock_mode or not self.api_token or not self.account_id:
                raw_result = self._execute_mock_inference(
                    detection_confidence=detection_confidence,
                    predicted_iou=predicted_iou,
                    area_pixels=area_pixels,
                    species_ambiguity=species_ambiguity,
                    has_image=has_image,
                    infestation_pct=infestation_pct,
                    max_allowed_infestation=max_allowed_infestation,
                    iou_threshold=iou_threshold,
                    min_confidence=min_confidence,
                    label=label,
                )
            else:
                prompt_payload = {
                    "model": self.model_name,
                    "prompt": (
                        f"Evaluate precision agriculture robotic spot-spray telemetry: {json.dumps(telemetry)}. "
                        "Candidate actions: ['ACCEPT', 'REFINE', 'ESCALATE_SYSTEM2', 'SUPPRESS_SPRAY']. "
                        "Return JSON with 'action', 'probabilities', and 'reason'."
                    ),
                    "image": encoded_image,
                }
                raw_result = self._execute_cloud_inference(prompt_payload)

            action, probs, confidence, reason = self._parse_probabilities(raw_result)
            latency = (time.perf_counter() - t0) * 1000.0

            return RouterDecision(
                action=action,
                reason=reason,
                latency_ms=round(latency, 4),
                backend=self.backend,
                confidence=confidence,
                probabilities=probs,
                metadata={
                    "multimodal_image_present": has_image,
                    "model_name": self.model_name,
                    "mock_mode": self.mock_mode,
                },
            )

        except Exception as err:
            # FAIL-SAFE FALLBACK: Never drop an agricultural actuator decision due to network outage!
            latency = (time.perf_counter() - t0) * 1000.0
            logger.warning(
                "Clef Flash network/inference failure (%s). Triggering fail-safe local deterministic router.",
                err,
            )
            fallback_decision = self.fallback_router.route(
                detection_confidence=detection_confidence,
                predicted_iou=predicted_iou,
                area_pixels=area_pixels,
                species_ambiguity=species_ambiguity,
                image_crop=image_crop,
                infestation_pct=infestation_pct,
                max_allowed_infestation=max_allowed_infestation,
                iou_threshold=iou_threshold,
                min_confidence=min_confidence,
                label=label,
            )
            return RouterDecision(
                action=fallback_decision.action,
                reason=f"[Clef Flash Fallback: {err}] {fallback_decision.reason}",
                latency_ms=round(latency + fallback_decision.latency_ms, 4),
                backend=self.backend,
                confidence=fallback_decision.confidence,
                probabilities=fallback_decision.probabilities,
                metadata={
                    "fallback_triggered": True,
                    "fallback_reason": str(err),
                    "fallback_backend": fallback_decision.backend.value,
                },
            )
