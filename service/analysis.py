"""Run the AgriAgent pipeline on one image and package the result for the API and database.

This module only calls existing pipeline functions (app/components/pipeline.py and the
visualisation helpers) in the same way the Streamlit app does. It adds no new vision logic.
"""

from __future__ import annotations

import hashlib
import io
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np
from PIL import Image

from app.components.pipeline import build_spray_geojson, execute_agriagent_workflow, extract_kpis
from app.components.ui import plant_verdict_image
from service import config
from service.validation import AnalysisParams
from src.vision.visualization import draw_boxes, outline_masks, overlay_masks

# Real mode shares one set of loaded models (Grounding DINO + SAM 2) on one GPU. They are not
# safe to call from several threads at once, so real-mode requests take turns. Mock mode is
# plain NumPy per request and runs in parallel.
_REAL_MODE_LOCK = threading.Lock()


class AnalysisFailed(RuntimeError):
    """The pipeline itself raised. The API answers 500 with this message."""


@dataclass
class AnalysisResult:
    record: Dict[str, Any]  # one row for RunStore.add
    geojson: Dict[str, Any]


def _json_default(value: Any) -> Any:
    """json.dumps cannot write NumPy numbers; the GeoJSON builder can return them."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


def approved_masks(final_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Masks the safety gate approved for spraying (same source as the Streamlit view)."""
    artifact = (final_state.get("artifacts") or {}).get("spray_map")
    zones = (getattr(artifact, "payload", None) or {}).get("approved_spray_zones", [])
    return [
        {"mask_array": np.asarray(zone["mask"], dtype=bool), "label": zone["label"]}
        for zone in zones
    ]


def render_overlay(
    image: Image.Image, final_state: Dict[str, Any], min_confidence: float
) -> Image.Image:
    """Approved spray zones in colour, detection boxes on top, zone outlines last."""
    masks = approved_masks(final_state)
    boxes = [b for b in final_state.get("boxes", []) if b.get("score", 0.0) >= min_confidence]
    view = overlay_masks(image, masks, alpha=0.45)
    view = draw_boxes(view, boxes)
    return outline_masks(view, [m["mask_array"] for m in masks])


def encode_jpeg(image: Image.Image) -> bytes:
    small = image.copy()
    small.thumbnail((config.OVERLAY_MAX_SIDE, config.OVERLAY_MAX_SIDE))
    buf = io.BytesIO()
    small.convert("RGB").save(buf, format="JPEG", quality=config.OVERLAY_JPEG_QUALITY)
    return buf.getvalue()


def run_analysis(
    image: Image.Image, raw: bytes, filename: str, params: AnalysisParams
) -> AnalysisResult:
    mock = params.mode == "mock"
    started = time.perf_counter()
    try:
        if mock:
            final_state = _run_pipeline(image, params, mock=True)
        else:
            with _REAL_MODE_LOCK:
                final_state = _run_pipeline(image, params, mock=False)
    except Exception as exc:
        raise AnalysisFailed(str(exc)) from exc
    duration_ms = (time.perf_counter() - started) * 1000.0

    spray_map = final_state.get("spray_map") or {}
    kpis = extract_kpis(spray_map)
    _, counts = plant_verdict_image(image, final_state)
    geojson = build_spray_geojson(final_state, crop=params.crop)
    overlay = encode_jpeg(render_overlay(image, final_state, params.min_confidence))

    record = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "filename": (filename or "upload")[:255],
        "image_sha256": hashlib.sha256(raw).hexdigest(),
        "width": image.width,
        "height": image.height,
        "crop": params.crop,
        "mode": params.mode,
        "min_confidence": params.min_confidence,
        "safety_action": str(spray_map.get("safety_action", "UNKNOWN")),
        "spray_allowed": int(bool(spray_map.get("spray_allowed", False))),
        "status": kpis["status"],
        "weed_count": kpis["weed_count"],
        "withheld_count": len(spray_map.get("withheld_masks") or []),
        "infestation_pct": kpis["infestation_percentage"],
        "savings_pct": kpis["chemical_savings_percentage"],
        "sprayed_px": int(counts.get("sprayed", 0)),
        "crop_px": int(counts.get("crop", 0)),
        "unsure_px": int(counts.get("unsure", 0)),
        "system2_needed": int(bool(final_state.get("system2_needed", False))),
        "duration_ms": round(duration_ms, 3),
        "geojson": json.dumps(geojson, default=_json_default),
        "overlay_jpeg": overlay,
    }
    return AnalysisResult(record=record, geojson=geojson)


def _run_pipeline(image: Image.Image, params: AnalysisParams, mock: bool) -> Dict[str, Any]:
    # Same arguments as app/app.py: plant rules in real mode only, no external agent calls.
    return execute_agriagent_workflow(
        image=image,
        mock_mode=mock,
        iou_threshold=0.85,
        buffer_pixels=10,
        crop=params.crop,
        min_confidence=params.min_confidence,
        use_agent=False,
        plant_rules=not mock,
    )
