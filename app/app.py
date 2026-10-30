"""
app/app.py
AgriAgent Interactive Streamlit Application.
Dual-Brain Multi-Agent Precision Agriculture (VJTI FYP).

Architecture:
  - System 1 (Local Real-Time Reflex, <40 ms): Grounding DINO detection + SAM 2 instance
    segmentation + morphological closed-loop refinement + precision spray map generation.
  - System 2 (Deliberative Agronomic Intelligence): Ambiguous weed diagnosis via VLM +
    evidence-based retrieval over statutory ICAR/CIBRC knowledge corpus + dosage ceiling checks.
"""

import hashlib
import logging
from pathlib import Path
import sys

import numpy as np
from typing import Any, Dict, Optional, Tuple
from PIL import Image

# Put the repository root first on sys.path. `streamlit run app/app.py` puts app/ first,
# where `import app` would find this file instead of the app package. An editable install
# may already list the root later in sys.path, so it must be moved, not only added.
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from app.components.pipeline import (
    ImageDecodeError,
    build_spray_geojson,
    create_sample_field_image,
    decode_uploaded_image,
    execute_agriagent_workflow,
    extract_kpis,
    format_prescription_report,
)
from app.components.ui import (
    render_farmer_summary,
    render_geojson_download,
    render_mode_badge,
    render_agent_toggle,
    render_crop_warning,
    render_header,
    render_kpi_cards,
    render_prescription_report,
    render_sidebar,
    render_visualizations,
)
from src.vision.visualization import draw_boxes, overlay_masks

try:
    import streamlit as st
except ImportError:
    st = None

logger = logging.getLogger("agriagent.app")


def run_pipeline_on_image(
    image: Image.Image,
    mock_mode: bool = True,
    text_prompt: Optional[str] = None,
    confidence_threshold: float = 0.3,
    nozzle_buffer: int = 10,
    crop: str = "cotton",
    force_system2: bool = False,
    use_agent: bool = False,
) -> Tuple[Image.Image, Dict[str, Any], Dict[str, Any]]:
    """
    Core business logic function: Runs VisionWorkflowRunner on an input image,
    generates annotated visualization overlays, and extracts dynamic KPIs.

    Args:
        image: Source field PIL image.
        mock_mode: Toggle between mock and live model inference.
        text_prompt: Zero-shot prompt for Grounding DINO; None means default_prompt(crop).
        confidence_threshold: Bounding box score threshold.
        nozzle_buffer: Physical spray buffer margin in pixels.
        crop: Agricultural crop type.
        force_system2: Whether to force deliberative System 2 prescription.
        use_agent: Let the escalation agent review withheld plants (real mode only).

    Returns:
        (annotated_image, final_state, kpis)
    """
    final_state = execute_agriagent_workflow(
        image=image,
        mock_mode=mock_mode,
        text_prompt=text_prompt,
        iou_threshold=0.85,
        buffer_pixels=nozzle_buffer,
        crop=crop,
        force_system2=force_system2,
        min_confidence=confidence_threshold,
        use_agent=use_agent and not mock_mode,
        plant_rules=not mock_mode,
    )

    boxes = final_state.get("boxes", [])
    # Filter boxes by confidence threshold
    filtered_boxes = [b for b in boxes if b.get("score", 0.0) >= confidence_threshold]

    # Paint only the zones the safety gate approved: painting every mask made crop or
    # withheld plants look sprayed.
    spray_artifact = (final_state.get("artifacts") or {}).get("spray_map")
    approved = (getattr(spray_artifact, "payload", None) or {}).get("approved_spray_zones", [])
    approved_masks = [
        {"mask_array": np.asarray(zone["mask"], dtype=bool), "label": zone["label"]}
        for zone in approved
    ]

    # Generate composite visualization overlay
    viz_image = overlay_masks(image, approved_masks, alpha=0.45)
    viz_image = draw_boxes(viz_image, filtered_boxes)

    # Dynamic KPIs extracted directly from spray_map
    kpis = extract_kpis(final_state.get("spray_map"))

    return viz_image, final_state, kpis


def main() -> None:
    """Main Streamlit application entrypoint."""
    if st is None:
        print("Streamlit is not installed in the active environment.")
        return

    st.set_page_config(
        page_title="AgriAgent Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 1. Main Header
    render_header()

    # 2. Sidebar Controls
    (
        mock_mode,
        crop,
        text_prompt,
        confidence_threshold,
        nozzle_buffer,
        force_system2,
    ) = render_sidebar()
    use_agent = render_agent_toggle(mock_mode)

    # 3. Image Upload Section with Exception Handling
    st.subheader("Field Sensor Stream")
    uploaded_file = st.file_uploader(
        "Upload Field Drone / Handheld Photo",
        type=["jpg", "jpeg", "png"],
        help="Upload an aerial RGB photo or handheld sensor image of the crop canopy.",
    )

    use_sample = False
    if uploaded_file is None:
        use_sample = st.checkbox(
            "Or use sample field photo for instant preview",
            value=True,
            help="Generates synthetic organic crop foliage with weed patches.",
        )

    image: Optional[Image.Image] = None
    if uploaded_file is not None:
        try:
            image = decode_uploaded_image(uploaded_file)
            st.success("Sensor stream image loaded and decoded successfully.")
        except ImageDecodeError as exc:
            st.error(f"Image Decoding Error: {exc}. Please verify file integrity and format.")
            return
        except Exception as exc:
            st.error(f"Unexpected error loading file: {exc}")
            return
    elif use_sample:
        image = create_sample_field_image()
    else:
        st.info("Please upload a field photo (JPG, JPEG, or PNG) above to start the pipeline.")
        return

    if not text_prompt.strip(" ."):
        st.error(
            "The detection prompt is empty. Enter what to look for, e.g. 'weed . cotton plant .'"
        )
        return

    # 4. Pipeline Execution
    with st.spinner(
        "Executing System-1 Reflex Perception Pipeline..."
        if mock_mode
        else "Executing Live Deep Learning Backbones (Grounding DINO + SAM 2)..."
    ):
        try:
            # F20: Streamlit reruns this script on every click (language, download, ...). Reuse
            # the last result unless the photo or a setting changed, so a click costs no model
            # calls and no GPU time.
            run_key = (
                hashlib.sha256(image.tobytes()).hexdigest(),
                image.size,
                mock_mode,
                text_prompt,
                confidence_threshold,
                nozzle_buffer,
                crop,
                force_system2,
                use_agent,
            )
            cached = st.session_state.get("last_run")
            if cached and cached[0] == run_key:
                viz_image, final_state, kpis = cached[1]
            else:
                viz_image, final_state, kpis = run_pipeline_on_image(
                    image=image,
                    mock_mode=mock_mode,
                    text_prompt=text_prompt,
                    confidence_threshold=confidence_threshold,
                    nozzle_buffer=nozzle_buffer,
                    crop=crop,
                    force_system2=force_system2,
                    use_agent=use_agent,
                )
                st.session_state["last_run"] = (run_key, (viz_image, final_state, kpis))
        except Exception as exc:
            st.error(f"Pipeline Execution Failed: {exc}")
            logger.error("Error executing pipeline in app: %s", exc, exc_info=True)
            return

    if final_state.get("error"):
        st.error(f"Pipeline stopped: {final_state['error']}")
        return

    # 5. Dynamic KPI Metric Cards
    render_mode_badge(mock_mode)
    render_crop_warning(final_state, crop)
    render_kpi_cards(kpis)

    st.divider()

    # 6. Two-Column Visualizer
    render_visualizations(original_image=image, annotated_image=viz_image)

    # 7. System 2 Deliberative Prescription Report
    prescription_data = format_prescription_report(final_state.get("prescription_report"))
    vlm_reasoning = final_state.get("vlm_reasoning")
    render_prescription_report(prescription_data, vlm_reasoning=vlm_reasoning, mock_mode=mock_mode)
    render_farmer_summary(final_state, crop=crop, mock_mode=mock_mode)

    st.divider()

    # 8. GeoJSON Prescription Download
    geojson_doc = build_spray_geojson(
        final_state=final_state,
        crop=crop,
        nozzle_buffer_cm=nozzle_buffer,
    )
    render_geojson_download(geojson_doc)


if __name__ == "__main__":
    # `streamlit run` executes this file as __main__; tests import it and never load .env.
    # Provider keys (GROQ_API_KEY, ...) live there; without them System 2 cannot answer.
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(PROJECT_ROOT) / ".env")
    except ImportError:
        pass
    main()
