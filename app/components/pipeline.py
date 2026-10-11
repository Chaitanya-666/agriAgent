"""
app/components/pipeline.py
Core pipeline execution, image decoding, KPI calculation, and GeoJSON export.
Connects Streamlit UI directly to VisionWorkflowRunner and System 2 Agronomy Engine.
"""

import io
import logging
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image

from src.agronomy.prescription import get_herbicide_prescription
from src.workflow import VisionWorkflowRunner, create_initial_state

logger = logging.getLogger("agriagent.app.pipeline")


class ImageDecodeError(ValueError):
    """Raised when an uploaded file cannot be parsed or decoded into a valid image."""

    pass


def decode_uploaded_image(file_or_bytes: Any) -> Image.Image:
    """
    Safely decode uploaded file buffers, bytes, or PIL Image instances.

    Args:
        file_or_bytes: PIL.Image, file-like object with .read(), or raw bytes.

    Returns:
        PIL.Image converted to RGB.

    Raises:
        ImageDecodeError: On empty buffers, corrupt payloads, or unsupported formats.
    """
    if file_or_bytes is None:
        raise ImageDecodeError("No image data provided.")

    if isinstance(file_or_bytes, Image.Image):
        return file_or_bytes.convert("RGB")

    raw_bytes: bytes
    if hasattr(file_or_bytes, "read"):
        try:
            # Handle Streamlit UploadedFile or file-like buffer
            if hasattr(file_or_bytes, "seek"):
                file_or_bytes.seek(0)
            raw_bytes = file_or_bytes.read()
        except Exception as exc:
            raise ImageDecodeError(f"Failed to read file buffer: {exc}") from exc
    elif isinstance(file_or_bytes, (bytes, bytearray)):
        raw_bytes = bytes(file_or_bytes)
    else:
        raise ImageDecodeError(f"Unsupported image input type: {type(file_or_bytes).__name__}")

    if len(raw_bytes) == 0:
        raise ImageDecodeError("Uploaded image file is empty (0 bytes).")

    try:
        bio = io.BytesIO(raw_bytes)
        img = Image.open(bio)
        # Verify integrity and load pixels
        img.load()
        return img.convert("RGB")
    except Exception as exc:
        raise ImageDecodeError(f"Corrupt or invalid image payload: {exc}") from exc


def create_sample_field_image(width: int = 640, height: int = 480) -> Image.Image:
    """Generate a realistic mock field image for instant demonstration."""
    arr = np.full((height, width, 3), (125, 98, 68), dtype=np.uint8)
    noise = np.random.RandomState(42).randint(-15, 15, (height, width, 3))
    arr = np.clip(arr.astype(int) + noise, 0, 255).astype(np.uint8)

    # Simulated crop rows
    for x in range(80, width, 160):
        arr[:, max(0, x - 25) : min(width, x + 25)] = [52, 115, 42]

    # Simulated weed spots
    for wx, wy, rad in [(180, 160, 40), (420, 210, 48), (260, 360, 35)]:
        yy, xx = np.ogrid[
            max(0, wy - rad) : min(height, wy + rad),
            max(0, wx - rad) : min(width, wx + rad),
        ]
        circle = ((xx - wx) ** 2 + ((yy - wy) ** 2)) <= rad**2
        arr[
            max(0, wy - rad) : min(height, wy + rad),
            max(0, wx - rad) : min(width, wx + rad),
        ][circle] = [95, 195, 60]

    return Image.fromarray(arr)


def execute_agriagent_workflow(
    image: Image.Image,
    mock_mode: bool = True,
    text_prompt: str = "cotton weed . broadleaf plant .",
    iou_threshold: float = 0.85,
    buffer_pixels: int = 10,
    crop: str = "cotton",
    force_system2: bool = False,
    target_weed_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the dual-brain AgriAgent workflow from input image to spray map and prescription.

    Args:
        image: RGB PIL Image of field patch.
        mock_mode: If True, uses deterministic fast laptop reflex models.
        text_prompt: Zero-shot prompt for Grounding DINO detection.
        iou_threshold: IoU threshold triggering active morphological refinement.
        buffer_pixels: Spray nozzle expansion margin.
        crop: Agricultural crop context ("cotton", "sugar beet", "wheat", etc.).
        force_system2: Whether to unconditionally execute System 2 deliberative RAG.
        target_weed_hint: Optional weed species hint for System 2 prescription.

    Returns:
        final_state: Comprehensive GraphState dictionary.
    """
    clean_image = decode_uploaded_image(image)

    runner = VisionWorkflowRunner(
        mock_mode=mock_mode,
        iou_threshold=iou_threshold,
        buffer_pixels=buffer_pixels,
    )

    initial_state = create_initial_state(
        image=clean_image,
        text_prompt=text_prompt,
    )
    initial_state["field_metadata"] = {
        "crop": crop.lower().strip(),
        "application": "Site-Specific Weed Spraying",
        "mock_mode": mock_mode,
    }

    try:
        final_state = runner.run(initial_state)
    except Exception as exc:
        logger.error("VisionWorkflowRunner failed during execution: %s", exc, exc_info=True)
        raise RuntimeError(f"Workflow execution failure: {exc}") from exc

    # If System 2 was requested or escalated, ensure prescription report is present
    should_run_s2 = force_system2 or final_state.get("system2_needed", False)
    if should_run_s2 and not final_state.get("prescription_report"):
        weed_name = target_weed_hint
        if not weed_name:
            boxes = final_state.get("boxes", [])
            weed_boxes = [b for b in boxes if "weed" in b.get("label", "").lower()]
            if weed_boxes:
                weed_name = weed_boxes[0].get("label", "Trianthema")
            else:
                weed_name = "Trianthema"

        try:
            crop_name = crop.lower().strip()
            prescription = get_herbicide_prescription(
                weed_name=weed_name,
                crop_stage="vegetative",
                crop=crop_name,
            )
            final_state["prescription_report"] = prescription
            final_state["system2_needed"] = True
            if not final_state.get("vlm_reasoning"):
                final_state["vlm_reasoning"] = (
                    f"System 2 Escalation: Identified candidate botanical target '{weed_name}' "
                    f"in {crop_name} field. Retrieved statutory ICAR/CIBRC guidance."
                )
        except Exception as exc:
            logger.warning("System 2 prescription retrieval failed: %s", exc)

    return final_state


def extract_kpis(spray_map: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract and validate numerical Key Performance Indicators directly from spray_map contract.

    Args:
        spray_map: Dictionary contract generated by VisionWorkflowRunner.spray_map_node.

    Returns:
        Structured KPI dictionary with infestation_percentage, chemical_savings_percentage, weed_count.
    """
    if not spray_map:
        return {
            "infestation_percentage": 0.0,
            "chemical_savings_percentage": 100.0,
            "weed_count": 0,
            "buffer_pixels": 0,
            "status": "No Active Spray Zones",
        }

    infestation = float(spray_map.get("infestation_percentage", 0.0))
    savings = float(spray_map.get("chemical_savings_percentage", 100.0))
    weed_count = int(spray_map.get("weed_count", 0))
    buffer_pixels = int(spray_map.get("buffer_pixels", 10))
    status = str(spray_map.get("status", "Selective Spot-Spray Prescription Generated"))

    # Clamp bounds to ensure mathematical invariants [0, 100]
    infestation = max(0.0, min(100.0, infestation))
    savings = max(0.0, min(100.0, savings))

    return {
        "infestation_percentage": round(infestation, 2),
        "chemical_savings_percentage": round(savings, 2),
        "weed_count": max(0, weed_count),
        "buffer_pixels": buffer_pixels,
        "status": status,
    }


def format_prescription_report(prescription: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Format prescription dictionary into structured report for UI display.
    """
    if not prescription:
        return None

    citations_raw = prescription.get("citations", [])
    citations_formatted: List[Dict[str, Any]] = []
    for c in citations_raw:
        if isinstance(c, dict):
            citations_formatted.append(
                {
                    "source": c.get("source", "ICAR Bulletin"),
                    "page": c.get("page", 1),
                    "authority": c.get("authority", "ICAR / CIBRC"),
                    "text_snippet": c.get("text_snippet", ""),
                }
            )

    return {
        "status": prescription.get("status", "ok"),
        "crop": prescription.get("crop", "cotton"),
        "target_weed": prescription.get("target_weed", "Unknown weed"),
        "active_ingredient": prescription.get("active_ingredient"),
        "formulation": prescription.get("formulation"),
        "dosage_ai_g_per_ha": prescription.get("dosage_ai_g_per_ha"),
        "water_volume_l_per_ha": prescription.get("water_volume_l_per_ha"),
        "pre_harvest_interval_days": prescription.get("pre_harvest_interval_days"),
        "toxicity_band": prescription.get("toxicity_band", "BLUE"),
        "citations": citations_formatted,
        "disclaimer": prescription.get("disclaimer", ""),
        "safety_warning": prescription.get("safety_warning"),
        "dosage_clamped": prescription.get("dosage_clamped", False),
        "original_dosage_ai_g_per_ha": prescription.get("original_dosage_ai_g_per_ha"),
        "crop_stage": prescription.get("crop_stage", "vegetative"),
    }


def build_spray_geojson(
    final_state: Dict[str, Any],
    crop: str = "cotton",
    nozzle_buffer_cm: int = 10,
    field_id: str = "VJTI-FIELD-PLOT-01",
) -> Dict[str, Any]:
    """
    Generate valid GeoJSON FeatureCollection prescription from pipeline execution state.
    """
    spray_map = final_state.get("spray_map") or {}
    kpis = extract_kpis(spray_map)
    prescription = final_state.get("prescription_report") or {}
    boxes = final_state.get("boxes", [])

    features = []
    # Base GPS coordinate for research plot
    base_lon, base_lat = 72.8550, 19.0220
    scale = 0.00001

    for idx, box in enumerate(boxes):
        if "weed" not in box.get("label", "").lower():
            continue

        x1, y1 = box.get("x1", 0.0), box.get("y1", 0.0)
        x2, y2 = box.get("x2", 0.0), box.get("y2", 0.0)

        # Map pixel coordinates to GPS polygon
        p1 = [round(base_lon + x1 * scale, 6), round(base_lat + y1 * scale, 6)]
        p2 = [round(base_lon + x2 * scale, 6), round(base_lat + y1 * scale, 6)]
        p3 = [round(base_lon + x2 * scale, 6), round(base_lat + y2 * scale, 6)]
        p4 = [round(base_lon + x1 * scale, 6), round(base_lat + y2 * scale, 6)]

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[p1, p2, p3, p4, p1]],
                },
                "properties": {
                    "zone_id": f"NOZZLE_PULSE_{idx + 1:02d}",
                    "action": "SPRAY_ACTIVE",
                    "target": box.get("label", "Weed"),
                    "confidence": round(float(box.get("score", 0.9)), 2),
                    "active_ingredient": prescription.get(
                        "active_ingredient", "Pyrithiobac-sodium"
                    ),
                    "formulation": prescription.get("formulation", "10% EC"),
                    "dosage_ai_g_per_ha": prescription.get("dosage_ai_g_per_ha", 75.0),
                    "buffer_margin_cm": nozzle_buffer_cm,
                },
            }
        )

    geojson_doc = {
        "type": "FeatureCollection",
        "metadata": {
            "field_id": field_id,
            "crop": crop,
            "weed_infestation_area": f"{kpis['infestation_percentage']}%",
            "selective_chemical_reduction": f"{kpis['chemical_savings_percentage']}%",
            "weed_count": kpis["weed_count"],
            "spray_nozzle_buffer_cm": nozzle_buffer_cm,
            "status": kpis["status"],
            "statutory_status": prescription.get("status", "ok"),
        },
        "features": features,
    }
    return geojson_doc
