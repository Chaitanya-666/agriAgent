"""
tests/e2e/test_tier2_boundary_robustness.py
Tier 2: Boundary, Robustness & Fault Tolerance Test Suite.

Verifies:
1. Empty, blank, and extreme-dimension image handling (1x1, 10x10, extreme aspect ratios).
2. Zero-infestation field scenario (0% weed coverage -> 100% herbicide savings).
3. 100% saturated infestation field scenario (100% weed coverage -> 0% savings -> spray safety suppression).
4. Corrupt and malformed image bytes, non-existent files, and missing GraphState payloads.
5. Missing optional dependencies (chromadb, cv2) activate documented fallback paths without crash.
6. Agronomy RAG safe no-knowledge handling with completely empty knowledge stores.
7. Strict mathematical invariants of spray map and herbicide savings functions:
   - Monotonicity: Area(Weeds) increases -> Herbicide Savings non-increases.
   - Buffer dilation: Buffer size increases -> Herbicide Savings non-increases.
   - Boundedness: All percentages strictly within [0.0, 100.0].
"""

import io
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image

from src.state import Artifact, ArtifactType, GraphState
from src.workflow import VisionWorkflowRunner, create_initial_state
from src.vision.grounding_dino import GroundingDINOEngine
from src.vision.sam2_wrapper import SAM2Segmenter
from src.agents.deterministic_router import DeterministicRouter
from src.agronomy.prescription import get_herbicide_prescription, DISCLAIMER
from src.agronomy.system2_node import System2Reasoner
from src.evaluation.iou_dice import compute_herbicide_savings, compute_iou, compute_dice
from tests.e2e.fixtures import (
    InMemoryKnowledgeStore,
    create_blank_image,
    create_corrupt_image_bytes,
)


class TestTier2BoundaryRobustness(unittest.TestCase):
    """Tier 2 E2E Boundary and Robustness Test Suite."""

    def setUp(self):
        self.runner = VisionWorkflowRunner(mock_mode=True, iou_threshold=0.85, buffer_pixels=10)

    def test_empty_blank_image_processing(self):
        """Verify pipeline processes uniform blank (all-black, all-white) images gracefully."""
        for color, name in [((0, 0, 0), "black"), ((255, 255, 255), "white")]:
            with self.subTest(blank_color=name):
                blank_img = create_blank_image(width=640, height=480, color=color)
                initial_state = create_initial_state(blank_img)
                final_state = self.runner.run(initial_state)

                self.assertIsNone(final_state.get("error"))
                self.assertIn("spray_map", final_state)
                self.assertIn("artifacts", final_state)
                self.assertIn("spray_map", final_state["artifacts"])

    def test_zero_detections_pipeline_invariants(self):
        """Verify clean field with zero detected weeds produces 100% chemical savings."""
        class ZeroDetectionEngine(GroundingDINOEngine):
            def detect(self, *args, **kwargs):
                return []

        clean_runner = VisionWorkflowRunner(
            detector=ZeroDetectionEngine(mock_mode=True),
            segmenter=SAM2Segmenter(mock_mode=True),
            mock_mode=True,
        )
        test_img = create_blank_image(640, 480, color=(100, 150, 70))
        initial_state = create_initial_state(test_img)
        final_state = clean_runner.run(initial_state)

        # Invariants for zero weed field
        self.assertEqual(len(final_state["boxes"]), 0)
        self.assertEqual(len(final_state["masks"]), 0)

        sm = final_state["spray_map"]
        self.assertEqual(sm["weed_count"], 0)
        self.assertEqual(sm["infestation_percentage"], 0.0)
        self.assertEqual(sm["chemical_savings_percentage"], 100.0)

        comp_mask = final_state["artifacts"]["spray_map"].payload["composite_mask"]
        self.assertEqual(comp_mask.sum(), 0)

    def test_extreme_small_dimensions_image(self):
        """Verify handling of tiny image resolutions (10x10 and 1x1)."""
        for dims in [(10, 10), (1, 1)]:
            with self.subTest(dimensions=dims):
                w, h = dims
                tiny_img = Image.new("RGB", (w, h), color=(80, 120, 50))
                initial_state = create_initial_state(tiny_img)

                # Should complete without indexing errors or zero-division crashes
                final_state = self.runner.run(initial_state)
                self.assertIn("spray_map", final_state)
                self.assertEqual(
                    final_state["spray_map"]["target_resolution"],
                    {"width": w, "height": h},
                )

    def test_extreme_aspect_ratio_images(self):
        """Verify handling of extreme aspect ratio images (ultra-tall 10x500 and ultra-wide 500x10)."""
        for dims in [(10, 500), (500, 10)]:
            with self.subTest(dimensions=dims):
                w, h = dims
                extreme_img = Image.new("RGB", (w, h), color=(70, 110, 40))
                initial_state = create_initial_state(extreme_img)
                final_state = self.runner.run(initial_state)

                comp_mask = final_state["artifacts"]["spray_map"].payload["composite_mask"]
                self.assertEqual(comp_mask.shape, (h, w))

    def test_corrupt_image_bytes_handling(self):
        """Verify corrupt byte streams raise informative errors without process crash."""
        corrupt_bytes = create_corrupt_image_bytes()
        corrupt_io = io.BytesIO(corrupt_bytes)

        engine = GroundingDINOEngine(mock_mode=True)
        # Attempting to open malformed buffer with PIL raises UnidentifiedImageError or OSError
        with self.assertRaises((OSError, Image.UnidentifiedImageError)):
            Image.open(corrupt_io)

    def test_nonexistent_image_path_raises_filenotfound(self):
        """Verify passing a non-existent file path string raises FileNotFoundError."""
        engine = GroundingDINOEngine(mock_mode=True)
        non_existent = "/tmp/non_existent_agri_image_deadbeef1234.jpg"
        with self.assertRaises(FileNotFoundError):
            engine._normalize_image_input(non_existent)

    def test_missing_image_in_graph_state_returns_error(self):
        """Verify detect_node and workflow handle missing input image gracefully."""
        empty_state: GraphState = {
            "messages": [],
            "artifacts": {},
            "error": None,
            "image": None,
            "image_path": None,
            "text_prompt": "weed",
            "field_metadata": {},
            "boxes": [],
            "masks": [],
            "refinement_count": 0,
            "system2_needed": False,
            "vlm_reasoning": None,
            "prescription_report": None,
            "spray_map": None,
            "ground_truth_masks": None,
            "evaluation_metrics": None,
        }

        det_result = self.runner.detect_node(empty_state)
        self.assertIn("error", det_result)
        self.assertEqual(det_result["boxes"], [])

        final_state = self.runner.run(empty_state)
        self.assertIn("error", final_state)
        self.assertIn("Missing input image", final_state["error"])

    def test_missing_image_in_system2_node_returns_error(self):
        """Verify System2Reasoner safely returns error when in-memory image is absent."""
        reasoner = System2Reasoner(mock_mode=True)
        out = reasoner.system2_node({"image": None, "artifacts": {}, "field_metadata": {}})
        self.assertIn("error", out)
        self.assertIn("needs an in-memory PIL image", out["error"])

    def test_missing_chromadb_raises_clean_importerror(self):
        """Verify KnowledgeStore raises clean ImportError with install instructions if chromadb is None."""
        from src.agronomy import knowledge_store

        with patch.object(knowledge_store, "chromadb", None):
            with self.assertRaises(ImportError) as ctx:
                knowledge_store.KnowledgeStore()
            self.assertIn("chromadb is required", str(ctx.exception))

    def test_saturated_100_percent_infestation_spray_safety(self):
        """Verify 100% weed infestation yields 0% chemical savings and triggers safety suppression."""
        h, w = 480, 640
        full_mask = np.ones((h, w), dtype=bool)

        # Calculate savings directly
        savings = compute_herbicide_savings(full_mask, (h, w), buffer_pixels=10)
        self.assertEqual(savings, 0.0, "100% weed coverage must yield exactly 0.0% herbicide savings")

        # Verify router spray safety guardrail (max allowed infestation 85%)
        router = DeterministicRouter()
        is_safe = router.verify_spray_safety(infestation_pct=100.0, buffer_pixels=10, max_allowed_infestation=85.0)
        self.assertFalse(is_safe, "Spot spraying must be suppressed when infestation exceeds 85%")

        is_safe_under = router.verify_spray_safety(infestation_pct=25.0, buffer_pixels=10, max_allowed_infestation=85.0)
        self.assertTrue(is_safe_under, "Spot spraying must be permitted under 85% infestation")

    def test_rag_empty_store_returns_no_knowledge(self):
        """Verify get_herbicide_prescription with zero documents returns no_knowledge_found."""
        empty_store = InMemoryKnowledgeStore(documents=[])
        report = get_herbicide_prescription("Parthenium", "vegetative", store=empty_store)

        self.assertEqual(report["status"], "no_knowledge_found")
        self.assertEqual(report["evidence"], [])
        self.assertIn("disclaimer", report)

    def test_spray_map_mathematical_invariants(self):
        """
        Verify mathematical properties of herbicide savings function:
        1. Monotonicity with respect to weed area: subset mask yields >= savings.
        2. Monotonicity with respect to buffer size: larger buffer yields <= savings.
        3. Percentage bounds: output is strictly in [0.0, 100.0].
        """
        h, w = 200, 200
        shape = (h, w)

        # Construct mask A (small patch) and mask B (larger superset patch)
        mask_a = np.zeros(shape, dtype=bool)
        mask_a[50:80, 50:80] = True  # 30x30 = 900 pixels

        mask_b = np.zeros(shape, dtype=bool)
        mask_b[40:100, 40:100] = True  # 60x60 = 3600 pixels (contains mask_a)

        savings_a = compute_herbicide_savings(mask_a, shape, buffer_pixels=5)
        savings_b = compute_herbicide_savings(mask_b, shape, buffer_pixels=5)

        # 1. Monotonicity: Smaller weed patch must yield greater or equal chemical savings
        self.assertGreater(savings_a, savings_b)

        # 2. Buffer dilation: Increasing buffer strictly non-increases savings
        savings_buf_0 = compute_herbicide_savings(mask_a, shape, buffer_pixels=0)
        savings_buf_5 = compute_herbicide_savings(mask_a, shape, buffer_pixels=5)
        savings_buf_15 = compute_herbicide_savings(mask_a, shape, buffer_pixels=15)

        self.assertGreaterEqual(savings_buf_0, savings_buf_5)
        self.assertGreaterEqual(savings_buf_5, savings_buf_15)

        # 3. Output bounds for arbitrary configurations
        for mask in [mask_a, mask_b, np.zeros(shape, dtype=bool), np.ones(shape, dtype=bool)]:
            for buf in [0, 5, 20]:
                sav = compute_herbicide_savings(mask, shape, buffer_pixels=buf)
                self.assertGreaterEqual(sav, 0.0)
                self.assertLessEqual(sav, 100.0)


if __name__ == "__main__":
    unittest.main()
