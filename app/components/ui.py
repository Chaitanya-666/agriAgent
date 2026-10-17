"""
app/components/ui.py
Streamlit UI presentation components for AgriAgent dashboard.
Renders KPI metric cards, two-column visualizers, and System 2 statutory prescription reports.
"""

import json
from typing import Any, Dict, Optional, Tuple
from PIL import Image

from src.workflow import default_prompt

try:
    import streamlit as st
except ImportError:
    st = None


def render_header() -> None:
    """Render main application banner and architecture description."""
    if st is None:
        return
    st.title("AgriAgent: Dual-Brain Multi-Agent Precision Agriculture (VJTI FYP)")
    st.caption(
        "Autonomous Edge Perception (System 1 Grounding DINO + SAM 2 Reflex) & "
        "Statutory Deliberative Agronomy (System 2 ICAR / CIBRC RAG)"
    )


def render_sidebar() -> Tuple[bool, str, str, float, int, bool]:
    """
    Render pipeline configuration controls in the sidebar.

    Returns:
        (mock_mode, crop, prompt, confidence_threshold, nozzle_buffer, force_system2)
    """
    if st is None:
        return True, "Cotton", default_prompt("Cotton"), 0.3, 10, False

    st.sidebar.header("Execution Controls")

    # Explicit toggle: Mock Mode (Fast Laptop Demo) vs Live Model Inference
    mock_mode = st.sidebar.checkbox(
        "Mock Mode (Fast Laptop Demo)",
        value=True,
        help="Use deterministic edge reflex models (<40 ms) without requiring GPU weights or API keys.",
    )

    if mock_mode:
        st.sidebar.info("Running in Mock Reflex Mode: Deterministic synthetic inference active.")
    else:
        st.sidebar.warning(
            "Live Model Inference Selected: Requires CUDA GPU (SAM 2 / Grounding DINO) "
            "or active API keys for hosted providers."
        )

    st.sidebar.divider()
    st.sidebar.subheader("Agronomic Parameters")

    crop = st.sidebar.selectbox(
        "Crop Context",
        options=["Cotton", "Sugar Beet", "Wheat", "Rice"],
        index=0,
        help="Target crop used for statutory CIBRC dosage validation and species triage.",
    )

    text_prompt = st.sidebar.text_input(
        "Zero-Shot Detection Prompt",
        value=default_prompt(crop),
        key=f"prompt_{crop}",  # a new crop resets the box to that crop's default prompt
        help="Natural language prompt provided to Grounding DINO zero-shot detector.",
    )

    confidence_threshold = st.sidebar.slider(
        "Detection Confidence Threshold",
        min_value=0.1,
        max_value=0.9,
        value=0.3,
        step=0.05,
    )

    nozzle_buffer = st.sidebar.slider(
        "Spray Nozzle Buffer (pixels)",
        min_value=5,
        max_value=30,
        value=10,
        step=1,
        format="%d px",
        help="Expansion margin applied to segmented weed masks to prevent crop drift.",
    )

    force_system2 = st.sidebar.checkbox(
        "Force System 2 Statutory Consultation",
        value=False,
        help="Trigger statutory ICAR/CIBRC herbicide retrieval and dosage verification regardless of confidence.",
    )

    return mock_mode, crop, text_prompt, confidence_threshold, nozzle_buffer, force_system2


def render_kpi_cards(kpis: Dict[str, Any]) -> None:
    """Render high-contrast dynamic KPI metric cards directly from spray_map."""
    if st is None:
        return

    st.subheader("Field Agronomic Metrics (Direct Pipeline Telemetry)")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Weed Infestation Area",
            value=f"{kpis.get('infestation_percentage', 0.0):.1f}%",
            help="Total field surface area covered by verified weed foliage.",
        )

    with col2:
        st.metric(
            label="Chemical Volume Saved",
            value=f"{kpis.get('chemical_savings_percentage', 100.0):.1f}%",
            delta="Saved vs Broadcast",
            delta_color="normal",
            help="Active herbicide volume preserved by spot-spraying compared to uniform broadcast.",
        )

    with col3:
        st.metric(
            label="Target Weed Clusters",
            value=str(kpis.get("weed_count", 0)),
            help="Number of discrete botanical weed instances segmented by SAM 2.",
        )

    with col4:
        st.metric(
            label="Spray Margin Buffer",
            value=f"{kpis.get('buffer_pixels', 10)} px",
            help="Physical nozzle safety expansion radius.",
        )


def render_visualizations(original_image: Image.Image, annotated_image: Image.Image) -> None:
    """Render original sensor stream alongside precision spray overlay in two columns."""
    if st is None:
        return

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Original Field Sensor Stream")
        st.image(original_image, use_container_width=True)

    with col_right:
        st.subheader("Precision Spray Map & Segmented Foliage")
        st.image(annotated_image, use_container_width=True)


def render_prescription_report(
    prescription: Optional[Dict[str, Any]],
    vlm_reasoning: Optional[str] = None,
) -> None:
    """
    Render System 2 deliberative agronomy prescription report with statutory citations,
    active ingredients, dosage ceilings, and toxicity badges.
    """
    if st is None:
        return

    st.divider()
    st.subheader("System 2: Statutory Agronomic Reasoning & Prescription (ICAR / CIBRC)")

    if not prescription:
        st.info(
            "System 1 Fast Reflex Triage accepted detections without requiring deliberative escalation. "
            "Enable 'Force System 2 Statutory Consultation' in the sidebar to review verified chemical prescriptions."
        )
        return

    status = prescription.get("status", "ok")

    if status == "ok":
        st.success("Status: VERIFIED & APPROVED UNDER STATUTORY ICAR / CIBRC PROTOCOLS")
    elif status == "unapproved_chemical_flagged":
        st.error("Status: BANNED OR UNAPPROVED CHEMICAL INTERCEPTED")
    elif status == "no_knowledge_found":
        st.warning("Status: NO STATUTORY EVIDENCE FOUND — ZERO CHEMICALS PRESCRIBED")
    else:
        st.info(f"Status: {status.upper()}")

    # Display VLM visual reasoning if available
    if vlm_reasoning:
        with st.expander("Visual Diagnostic Reasoning (VLM Critic)", expanded=False):
            st.write(vlm_reasoning)

    # Display statutory safety warning banner if dosage was clamped or banned chemical intercepted
    warning = prescription.get("safety_warning")
    if warning:
        st.warning(f"Statutory Safety Warning: {warning}")

    if status == "ok":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("**Target Weed:**")
            st.write(prescription.get("target_weed", "Unknown"))
        with col2:
            st.markdown("**Active Ingredient:**")
            st.write(prescription.get("active_ingredient", "N/A"))
        with col3:
            st.markdown("**Approved Formulation:**")
            st.write(prescription.get("formulation", "N/A"))
        with col4:
            band = prescription.get("toxicity_band", "BLUE")
            st.markdown("**CIBRC Toxicity Band:**")
            st.write(f"🏷️ `{band}` Label")

        col5, col6, col7, col8 = st.columns(4)
        with col5:
            dosage = prescription.get("dosage_ai_g_per_ha")
            st.markdown("**Statutory Dosage Rate:**")
            st.write(f"{dosage:.1f} g a.i./ha" if dosage is not None else "N/A")
        with col6:
            water = prescription.get("water_volume_l_per_ha")
            st.markdown("**Water Dilution:**")
            st.write(f"{water:.0f} L/ha" if water is not None else "N/A")
        with col7:
            phi = prescription.get("pre_harvest_interval_days")
            st.markdown("**Pre-Harvest Interval (PHI):**")
            st.write(f"{phi} Days" if phi is not None else "N/A")
        with col8:
            crop_stage = prescription.get("crop_stage", "vegetative")
            st.markdown("**Crop Growth Stage:**")
            st.write(crop_stage.capitalize())

        # Statutory Citations Expander
        citations = prescription.get("citations", [])
        with st.expander(
            f"Regulatory Evidence & Citations ({len(citations)} sources)", expanded=True
        ):
            if citations:
                for idx, cite in enumerate(citations, 1):
                    st.markdown(
                        f"**[{idx}] {cite.get('authority', 'ICAR')} — {cite.get('source', 'Bulletin')}, "
                        f"Page {cite.get('page', 1)}**"
                    )
                    snippet = cite.get("text_snippet", "")
                    if snippet:
                        st.caption(f"> {snippet}")
            else:
                st.write("No direct citations attached.")

    # Statutory Disclaimer
    disclaimer = prescription.get("disclaimer")
    if disclaimer:
        st.caption(f"⚖️ **Statutory Notice:** {disclaimer}")


def render_geojson_download(geojson_data: Dict[str, Any]) -> None:
    """Render download button for precision spray GeoJSON prescription."""
    if st is None:
        return

    st.download_button(
        label="Download Field Prescription (GeoJSON)",
        data=json.dumps(geojson_data, indent=2),
        file_name="agriagent_spray_prescription.geojson",
        mime="application/geo+json",
        help="Export GPS-referenced nozzle pulse coordinates for autonomous drone or tractor sprayers.",
    )
