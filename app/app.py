"""
app/app.py
AgriAgent Week 1 Mock Streamlit Dashboard.
Dual-Brain Multi-Agent Precision Agriculture (VJTI FYP).
"""

import json
from pathlib import Path
import sys
from typing import List, Tuple

import numpy as np
from PIL import Image
import streamlit as st

# Ensure repository root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.state import Box, Mask
from src.vision.visualization import draw_boxes, overlay_masks


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
        circle = ((xx - wx) ** 2 + ((yy - wy) ** 2)) <= rad ** 2
        arr[
            max(0, wy - rad) : min(height, wy + rad),
            max(0, wx - rad) : min(width, wx + rad),
        ][circle] = [95, 195, 60]

    return Image.fromarray(arr)


def generate_mock_detections(
    image: Image.Image,
    application: str,
    confidence_threshold: float,
) -> Tuple[List[Box], List[Mask]]:
    """Generates mock Box and Mask contracts to demonstrate Task 4.1 visualizer."""
    w, h = image.size

    if application == "Disease Auditing":
        presets = [
            (0.18, 0.22, 0.38, 0.44, "Disease", 0.89),
            (0.55, 0.32, 0.78, 0.58, "Disease", 0.76),
            (0.35, 0.65, 0.55, 0.85, "Crop", 0.92),
        ]
    elif application == "Stand Count":
        presets = [
            (0.15, 0.20, 0.35, 0.42, "Crop", 0.94),
            (0.42, 0.28, 0.60, 0.50, "Crop", 0.91),
            (0.68, 0.35, 0.88, 0.58, "Crop", 0.87),
        ]
    elif application == "Chlorosis":
        presets = [
            (0.20, 0.25, 0.45, 0.50, "Disease", 0.83),
            (0.52, 0.35, 0.75, 0.62, "Crop", 0.88),
        ]
    else:  # Site-Specific Weed Spraying (default)
        presets = [
            (0.18, 0.22, 0.38, 0.44, "Weed", 0.88),
            (0.55, 0.30, 0.78, 0.58, "Weed", 0.82),
            (0.32, 0.62, 0.52, 0.85, "Crop", 0.94),
        ]

    boxes: List[Box] = []
    masks: List[Mask] = []

    for rel_x1, rel_y1, rel_x2, rel_y2, label, score in presets:
        if score < confidence_threshold:
            continue

        abs_x1 = rel_x1 * w
        abs_y1 = rel_y1 * h
        abs_x2 = rel_x2 * w
        abs_y2 = rel_y2 * h

        box: Box = {
            "x1": round(abs_x1, 1),
            "y1": round(abs_y1, 1),
            "x2": round(abs_x2, 1),
            "y2": round(abs_y2, 1),
            "label": label,
            "score": round(score, 2),
        }
        boxes.append(box)

        # Generate realistic 2D elliptical binary mask inside box
        ix1, iy1 = int(round(abs_x1)), int(round(abs_y1))
        ix2, iy2 = int(round(abs_x2)), int(round(abs_y2))
        bw = max(1, ix2 - ix1)
        bh = max(1, iy2 - iy1)

        mask_arr = np.zeros((h, w), dtype=bool)
        yy, xx = np.ogrid[:bh, :bw]
        cx, cy = bw / 2.0, bh / 2.0
        rx, ry = max(1.0, bw * 0.42), max(1.0, bh * 0.42)
        ellipse = (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) <= 1.0
        mask_arr[iy1:iy2, ix1:ix2] = ellipse

        mask: Mask = {
            "mask_array": mask_arr,
            "predicted_iou": round(min(0.96, 0.85 + score * 0.1), 2),
            "box": box,
            "label": label,
        }
        masks.append(mask)

    return boxes, masks


def main():
    st.set_page_config(
        page_title="AgriAgent Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 1. Main Header
    st.title("AgriAgent: Dual-Brain Multi-Agent Precision Agriculture (VJTI FYP)")
    st.caption("Week 1 Milestone: Zero-Shot Foundation Vision & Selective Spray Dashboard")

    # 2. Sidebar Controls
    st.sidebar.header("Pipeline Controls")
    application = st.sidebar.selectbox(
        "Application",
        options=[
            "Site-Specific Weed Spraying",
            "Disease Auditing",
            "Stand Count",
            "Chlorosis",
        ],
        index=0,
    )

    confidence_threshold = st.sidebar.slider(
        "Detection Confidence",
        min_value=0.1,
        max_value=0.9,
        value=0.3,
        step=0.05,
    )

    nozzle_buffer = st.sidebar.slider(
        "Spray Nozzle Buffer",
        min_value=5,
        max_value=20,
        value=10,
        step=1,
        format="%d cm",
    )

    # 3. Image Upload
    st.subheader("Field Sensor Stream")
    uploaded_file = st.file_uploader(
        "Upload Field Image",
        type=["jpg", "jpeg", "png"],
        help="Upload an aerial drone photo or handheld camera image of the crop field",
    )

    use_sample = False
    if uploaded_file is None:
        use_sample = st.checkbox("Or use sample field photo for instant preview", value=True)

    if uploaded_file is not None:
        image = Image.open(uploaded_file).convert("RGB")
    elif use_sample:
        image = create_sample_field_image()
    else:
        image = None
        st.info("Please upload a field photo (JPG, JPEG, or PNG) above to view analysis.")
        return

    # 4. Generate Mock Visualizations using Task 4.1 functions
    boxes, masks = generate_mock_detections(
        image=image,
        application=application,
        confidence_threshold=confidence_threshold,
    )

    # Overlay masks (Crop=Green, Weed=Red, Disease=Yellow) and bounding boxes
    viz_image = overlay_masks(image, masks, alpha=0.45)
    viz_image = draw_boxes(viz_image, boxes)

    # 5. Main Visualizer: Two-Column / Panel Layout
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Original Field Photo")
        st.image(image, use_container_width=True)

    with col_right:
        st.subheader("Precision Spray Map")
        st.image(viz_image, use_container_width=True)

    st.divider()

    # 6. KPI Cards
    st.subheader("Field Agronomic Metrics")
    kpi_col1, kpi_col2 = st.columns(2)
    with kpi_col1:
        st.metric(
            label="Weed Infestation Area",
            value="18.2%",
        )
    with kpi_col2:
        st.metric(
            label="Selective Chemical Reduction",
            value="74.6%",
            delta="Saved vs broadcast spraying",
        )

    # 7. Status Banner
    st.success("Selective Spot-Spray Prescription Generated")

    # 8. Download Mock Spray Prescription
    prescription_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "field_id": "VJTI-COTTON-PLOT-01",
            "timestamp": "2026-10-04T12:00:00Z",
            "application": application,
            "confidence_threshold": confidence_threshold,
            "spray_nozzle_buffer_cm": nozzle_buffer,
            "weed_infestation_area": "18.2%",
            "selective_chemical_reduction": "74.6%",
            "status": "APPROVED_FOR_SPRAYING",
        },
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [72.8550, 19.0220],
                            [72.8552, 19.0220],
                            [72.8552, 19.0222],
                            [72.8550, 19.0222],
                            [72.8550, 19.0220],
                        ]
                    ],
                },
                "properties": {
                    "zone_id": "NOZZLE_PULSE_01",
                    "action": "SPRAY_ACTIVE",
                    "target": "Weed",
                    "chemical": "Pyrithiobac Sodium 10% EC",
                    "buffer_margin_cm": nozzle_buffer,
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [72.8554, 19.0221],
                            [72.8556, 19.0221],
                            [72.8556, 19.0223],
                            [72.8554, 19.0223],
                            [72.8554, 19.0221],
                        ]
                    ],
                },
                "properties": {
                    "zone_id": "NOZZLE_PULSE_02",
                    "action": "SPRAY_ACTIVE",
                    "target": "Weed",
                    "chemical": "Pyrithiobac Sodium 10% EC",
                    "buffer_margin_cm": nozzle_buffer,
                },
            },
        ],
    }

    st.download_button(
        label="Download Prescription (GeoJSON)",
        data=json.dumps(prescription_geojson, indent=2),
        file_name="mock_spray_prescription.geojson",
        mime="application/geo+json",
    )


if __name__ == "__main__":
    main()
