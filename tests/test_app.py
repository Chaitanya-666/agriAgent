"""
tests/test_app.py
Comprehensive unit tests verifying app/app.py and app/components/ helper functions,
robust image decoding, state processing, dynamic KPI extraction, GeoJSON export,
and mock execution.
"""

import io
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from PIL import Image

from app.app import main, run_pipeline_on_image
from app.components.pipeline import (
    ImageDecodeError,
    build_spray_geojson,
    create_sample_field_image,
    decode_uploaded_image,
    execute_agriagent_workflow,
    extract_kpis,
    format_prescription_report,
)
from src.state import Artifact, ArtifactType


class TestImageDecoding(unittest.TestCase):
    """Verifies robust exception handling and validation on sensor image decoding."""

    def test_decode_pil_image(self):
        """Passing an existing PIL.Image returns an RGB copy."""
        img = Image.new("RGBA", (100, 100), color=(50, 120, 20, 255))
        decoded = decode_uploaded_image(img)
        self.assertIsInstance(decoded, Image.Image)
        self.assertEqual(decoded.mode, "RGB")
        self.assertEqual(decoded.size, (100, 100))

    def test_decode_valid_bytes_png(self):
        """Decoding valid PNG bytes returns an RGB PIL.Image."""
        img = Image.new("RGB", (64, 48), color=(200, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw_bytes = buf.getvalue()

        decoded = decode_uploaded_image(raw_bytes)
        self.assertEqual(decoded.size, (64, 48))
        self.assertEqual(decoded.mode, "RGB")

    def test_decode_file_like_object(self):
        """Decoding a file-like buffer (e.g. Streamlit UploadedFile) succeeds."""
        img = Image.new("RGB", (80, 80), color=(10, 80, 150))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        decoded = decode_uploaded_image(buf)
        self.assertEqual(decoded.size, (80, 80))

    def test_decode_empty_bytes_raises_error(self):
        """Empty 0-byte buffer must raise an informative ImageDecodeError."""
        with self.assertRaises(ImageDecodeError) as ctx:
            decode_uploaded_image(b"")
        self.assertIn("0 bytes", str(ctx.exception))

    def test_decode_corrupt_bytes_raises_error(self):
        """Corrupted or truncated image bytes must raise ImageDecodeError."""
        corrupt_bytes = b"\x89PNG\r\n\x1a\nCorruptRandomPayloadBytes12345"
        with self.assertRaises(ImageDecodeError):
            decode_uploaded_image(corrupt_bytes)

    def test_decode_none_raises_error(self):
        """None input must raise ImageDecodeError."""
        with self.assertRaises(ImageDecodeError):
            decode_uploaded_image(None)

    def test_decode_unsupported_type_raises_error(self):
        """Unsupported object types raise ImageDecodeError."""
        with self.assertRaises(ImageDecodeError):
            decode_uploaded_image([1, 2, 3])  # type: ignore


class TestSampleImageGenerator(unittest.TestCase):
    """Verifies synthetic demo field photo generator."""

    def test_create_sample_field_image(self):
        """Produces a realistic 3-channel RGB image matching requested dimensions."""
        img = create_sample_field_image(width=320, height=240)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (320, 240))
        arr = np.array(img)
        self.assertEqual(arr.shape, (240, 320, 3))
        self.assertGreater(arr.mean(), 10.0)


class TestWorkflowExecutionAndKPIs(unittest.TestCase):
    """Verifies pipeline execution, dynamic KPI extraction, and state processing."""

    def setUp(self):
        self.image = Image.new("RGB", (640, 480), color=(110, 95, 60))

    def test_execute_agriagent_workflow_mock_mode(self):
        """Executes full workflow in mock mode and populates state contracts."""
        state = execute_agriagent_workflow(
            image=self.image,
            mock_mode=True,
            crop="cotton",
            force_system2=False,
        )
        self.assertIn("boxes", state)
        self.assertIn("masks", state)
        self.assertIn("spray_map", state)
        self.assertIn("artifacts", state)

        boxes = state["boxes"]
        self.assertGreater(len(boxes), 0)
        self.assertTrue(all("label" in b and "score" in b for b in boxes))

        masks = state["masks"]
        self.assertEqual(len(masks), len(boxes))
        self.assertTrue(all("mask_array" in m for m in masks))

        spray_map = state["spray_map"]
        self.assertIn("infestation_percentage", spray_map)
        self.assertIn("chemical_savings_percentage", spray_map)
        self.assertIn("weed_count", spray_map)

    def test_execute_workflow_with_forced_system2(self):
        """Forcing System 2 populates statutory prescription report."""
        state = execute_agriagent_workflow(
            image=self.image,
            mock_mode=True,
            crop="cotton",
            force_system2=True,
            target_weed_hint="Trianthema",
        )
        self.assertTrue(state.get("system2_needed"))
        prescription = state.get("prescription_report")
        self.assertIsNotNone(prescription)
        self.assertEqual(prescription.get("status"), "ok")
        self.assertIn("active_ingredient", prescription)
        self.assertIn("citations", prescription)

    def test_extract_kpis_normal(self):
        """Extracts valid KPIs from populated spray map."""
        spray_map = {
            "infestation_percentage": 14.25,
            "chemical_savings_percentage": 78.50,
            "weed_count": 5,
            "buffer_pixels": 12,
            "status": "Active Spray Map",
        }
        kpis = extract_kpis(spray_map)
        self.assertEqual(kpis["infestation_percentage"], 14.25)
        self.assertEqual(kpis["chemical_savings_percentage"], 78.50)
        self.assertEqual(kpis["weed_count"], 5)
        self.assertEqual(kpis["buffer_pixels"], 12)

    def test_extract_kpis_empty_or_none(self):
        """Safe default fallbacks when spray map is None or empty."""
        kpis = extract_kpis(None)
        self.assertEqual(kpis["infestation_percentage"], 0.0)
        self.assertEqual(kpis["chemical_savings_percentage"], 100.0)
        self.assertEqual(kpis["weed_count"], 0)

    def test_extract_kpis_clamped_bounds(self):
        """Clamps out-of-bound percentages to [0, 100]."""
        spray_map = {
            "infestation_percentage": -5.0,
            "chemical_savings_percentage": 115.0,
            "weed_count": -2,
        }
        kpis = extract_kpis(spray_map)
        self.assertEqual(kpis["infestation_percentage"], 0.0)
        self.assertEqual(kpis["chemical_savings_percentage"], 100.0)
        self.assertEqual(kpis["weed_count"], 0)

    def test_run_pipeline_on_image_full_integration(self):
        """Tests run_pipeline_on_image returns visualizer, state, and KPIs."""
        viz_image, state, kpis = run_pipeline_on_image(
            image=self.image,
            mock_mode=True,
            confidence_threshold=0.2,
            nozzle_buffer=10,
            crop="cotton",
            force_system2=True,
        )
        self.assertIsInstance(viz_image, Image.Image)
        self.assertEqual(viz_image.size, self.image.size)
        self.assertIsInstance(state, dict)
        self.assertIsInstance(kpis, dict)
        self.assertGreater(kpis["chemical_savings_percentage"], 0.0)


class TestPrescriptionFormattingAndGeoJSON(unittest.TestCase):
    """Verifies System 2 report data extraction and GeoJSON generation."""

    def test_format_prescription_report_ok(self):
        """Formats evidence-grounded prescription report."""
        raw_presc = {
            "status": "ok",
            "crop": "cotton",
            "target_weed": "Trianthema",
            "active_ingredient": "Pyrithiobac-sodium",
            "formulation": "10% EC",
            "dosage_ai_g_per_ha": 75.0,
            "water_volume_l_per_ha": 500.0,
            "pre_harvest_interval_days": 160,
            "toxicity_band": "BLUE",
            "citations": [
                {
                    "source": "icar_weed_handbook.pdf",
                    "page": 42,
                    "authority": "ICAR",
                    "text_snippet": "Recommended 75 g a.i./ha post-emergence.",
                }
            ],
            "disclaimer": "Statutory advisory.",
            "safety_warning": None,
        }
        formatted = format_prescription_report(raw_presc)
        self.assertIsNotNone(formatted)
        self.assertEqual(formatted["status"], "ok")
        self.assertEqual(formatted["active_ingredient"], "Pyrithiobac-sodium")
        self.assertEqual(len(formatted["citations"]), 1)
        self.assertEqual(formatted["citations"][0]["authority"], "ICAR")

    def test_format_prescription_report_none(self):
        """None input returns None."""
        self.assertIsNone(format_prescription_report(None))

    def test_build_spray_geojson(self):
        """Constructs valid GeoJSON FeatureCollection."""
        final_state = {
            "spray_map": {
                "infestation_percentage": 12.0,
                "chemical_savings_percentage": 82.0,
                "weed_count": 2,
                "status": "Approved",
                "spray_allowed": True,
                "safety_action": "ACCEPT",
            },
            "artifacts": {
                "spray_map": Artifact(
                    id="approved",
                    type=ArtifactType.SPRAY_MAP,
                    title="Approved zones",
                    payload={
                        "approved_spray_zones": [
                            {
                                "label": "weed",
                                "score": 0.88,
                                "mask": np.pad(
                                    np.ones((120, 100), dtype=np.uint8),
                                    ((60, 300), (50, 490)),
                                ),
                            }
                        ]
                    },
                )
            },
            "boxes": [
                {"x1": 50.0, "y1": 60.0, "x2": 150.0, "y2": 180.0, "label": "weed", "score": 0.88},
                {
                    "x1": 200.0,
                    "y1": 220.0,
                    "x2": 280.0,
                    "y2": 310.0,
                    "label": "crop",
                    "score": 0.94,
                },
            ],
            "prescription_report": {
                "status": "ok",
                "active_ingredient": "Pyrithiobac-sodium",
                "dosage_ai_g_per_ha": 75.0,
            },
        }
        geojson = build_spray_geojson(final_state, crop="cotton", nozzle_buffer_cm=10)
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertIn("metadata", geojson)
        self.assertEqual(geojson["metadata"]["crop"], "cotton")
        # The approved spray-map artifact supplies the sole export geometry.
        self.assertEqual(len(geojson["features"]), 1)
        feat = geojson["features"][0]
        self.assertEqual(feat["type"], "Feature")
        self.assertEqual(feat["geometry"]["type"], "Polygon")
        self.assertEqual(feat["properties"]["action"], "SPRAY_ACTIVE")
        self.assertEqual(feat["properties"]["active_ingredient"], "Pyrithiobac-sodium")


class TestAppMainFlow(unittest.TestCase):
    """Verifies main() execution with mock streamlit to ensure zero unhandled crashes."""

    @patch("app.components.ui.st")
    @patch("app.app.st")
    def test_main_with_mock_streamlit(self, mock_app_st, mock_ui_st):
        """Simulates Streamlit lifecycle running app.main()."""
        # Configure mock Streamlit UI components
        for st_mock in (mock_app_st, mock_ui_st):
            st_mock.set_page_config = MagicMock()
            st_mock.title = MagicMock()
            st_mock.caption = MagicMock()
            st_mock.header = MagicMock()
            st_mock.subheader = MagicMock()
            st_mock.divider = MagicMock()
            st_mock.info = MagicMock()
            st_mock.success = MagicMock()
            st_mock.warning = MagicMock()
            st_mock.error = MagicMock()
            st_mock.write = MagicMock()
            st_mock.markdown = MagicMock()
            st_mock.metric = MagicMock()
            st_mock.image = MagicMock()
            st_mock.file_uploader = MagicMock(return_value=None)
            st_mock.checkbox = MagicMock(return_value=True)  # use sample image
            st_mock.sidebar = MagicMock()
            st_mock.sidebar.header = MagicMock()
            st_mock.sidebar.subheader = MagicMock()
            st_mock.sidebar.divider = MagicMock()
            st_mock.sidebar.info = MagicMock()
            st_mock.sidebar.warning = MagicMock()
            st_mock.sidebar.checkbox = MagicMock(return_value=True)  # mock mode
            st_mock.sidebar.selectbox = MagicMock(return_value="Cotton")
            st_mock.sidebar.text_input = MagicMock(return_value="weed . broadleaf weed .")
            st_mock.sidebar.slider = MagicMock(side_effect=[0.3, 10])  # threshold, buffer
            st_mock.columns = MagicMock(
                side_effect=lambda spec: [
                    MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))
                ]
            )
            st_mock.spinner = MagicMock()
            st_mock.download_button = MagicMock()
            st_mock.expander = MagicMock()

        # Run main function
        main()

        # Verify page configuration and header were called
        mock_app_st.set_page_config.assert_called_once()
        mock_ui_st.title.assert_called_once()
        mock_ui_st.metric.assert_called()

    @patch("app.app.run_pipeline_on_image", side_effect=RuntimeError("Simulated pipeline failure"))
    @patch("app.components.ui.st")
    @patch("app.app.st")
    def test_main_handles_pipeline_exception_gracefully(
        self, mock_app_st, mock_ui_st, mock_run_pipeline
    ):
        """Asserts that main() handles exceptions from run_pipeline_on_image cleanly with st.error without raising NameError."""
        for st_mock in (mock_app_st, mock_ui_st):
            st_mock.set_page_config = MagicMock()
            st_mock.title = MagicMock()
            st_mock.caption = MagicMock()
            st_mock.header = MagicMock()
            st_mock.subheader = MagicMock()
            st_mock.divider = MagicMock()
            st_mock.info = MagicMock()
            st_mock.success = MagicMock()
            st_mock.warning = MagicMock()
            st_mock.error = MagicMock()
            st_mock.write = MagicMock()
            st_mock.markdown = MagicMock()
            st_mock.metric = MagicMock()
            st_mock.image = MagicMock()
            st_mock.file_uploader = MagicMock(return_value=None)
            st_mock.checkbox = MagicMock(return_value=True)
            st_mock.sidebar = MagicMock()
            st_mock.sidebar.header = MagicMock()
            st_mock.sidebar.subheader = MagicMock()
            st_mock.sidebar.divider = MagicMock()
            st_mock.sidebar.info = MagicMock()
            st_mock.sidebar.warning = MagicMock()
            st_mock.sidebar.checkbox = MagicMock(return_value=True)
            st_mock.sidebar.selectbox = MagicMock(return_value="Cotton")
            st_mock.sidebar.text_input = MagicMock(return_value="weed . broadleaf weed .")
            st_mock.sidebar.slider = MagicMock(side_effect=[0.3, 10])
            st_mock.columns = MagicMock(
                side_effect=lambda spec: [
                    MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))
                ]
            )
            st_mock.spinner = MagicMock()
            st_mock.download_button = MagicMock()
            st_mock.expander = MagicMock()

        # Run main function - should catch RuntimeError, call st.error and return cleanly
        main()

        mock_app_st.error.assert_called_once_with(
            "Pipeline Execution Failed: Simulated pipeline failure"
        )
        mock_ui_st.metric.assert_not_called()


if __name__ == "__main__":
    unittest.main()
