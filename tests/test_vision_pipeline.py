"""
tests/test_vision_pipeline.py
Unit and Integration Tests for AgriAgent System-1 Vision Pipeline.

Verifies:
1. Grounding DINO zero-shot detection and box coordinate contracts.
2. SAM 2 instance segmentation and mask format validation.
3. Active closed-loop IoU refinement with error centroid calculation.
4. End-to-end VisionWorkflowRunner state transitions and herbicide savings calculations.
"""

import unittest
import numpy as np
from PIL import Image

from src.state import Box, Mask
from src.vision.grounding_dino import GroundingDINOEngine, DetectionResult
from src.vision.sam2_wrapper import SAM2Segmenter, SegmentResult
from src.vision.refinement import compute_error_centroid, get_refinement_point, should_refine
from src.evaluation.iou_dice import compute_iou, compute_dice, compute_herbicide_savings
from src.workflow import VisionWorkflowRunner, create_initial_state


class TestGroundingDINO(unittest.TestCase):
    """Test suite for Grounding DINO detection wrapper."""

    def setUp(self):
        self.engine = GroundingDINOEngine(mock_mode=True)
        self.image = Image.new("RGB", (640, 480), color=(110, 160, 80))

    def test_mock_detection_generates_boxes(self):
        detections = self.engine.detect(self.image, text_prompt="cotton weed . broadleaf plant .")
        self.assertGreater(len(detections), 0)
        for det in detections:
            self.assertIsInstance(det, DetectionResult)
            self.assertGreaterEqual(det.confidence, 0.35)
            x1, y1, x2, y2 = det.box
            self.assertLess(x1, x2)
            self.assertLess(y1, y2)
            self.assertLessEqual(x2, 640)
            self.assertLessEqual(y2, 480)

    def test_detect_to_state_boxes(self):
        state_boxes = self.engine.detect_to_state_boxes(self.image)
        self.assertIsInstance(state_boxes, list)
        for b in state_boxes:
            self.assertIn("x1", b)
            self.assertIn("y1", b)
            self.assertIn("x2", b)
            self.assertIn("y2", b)
            self.assertIn("label", b)
            self.assertIn("score", b)


class TestSAM2Segmenter(unittest.TestCase):
    """Test suite for SAM 2 instance segmentation wrapper."""

    def setUp(self):
        self.segmenter = SAM2Segmenter(mock_mode=True, default_mock_iou=0.88)
        self.image = Image.new("RGB", (640, 480), color=(100, 140, 60))
        self.boxes: list[Box] = [
            {"x1": 50.0, "y1": 50.0, "x2": 200.0, "y2": 200.0, "label": "weed", "score": 0.9}
        ]

    def test_segment_boxes_generates_masks(self):
        masks = self.segmenter.segment_boxes(self.image, self.boxes)
        self.assertEqual(len(masks), 1)
        seg = masks[0]
        self.assertIsInstance(seg, SegmentResult)
        self.assertEqual(seg.mask_array.shape, (480, 640))
        self.assertEqual(seg.mask_array.dtype, bool)
        self.assertGreater(seg.area_pixels, 0)
        self.assertGreater(seg.predicted_iou, 0.0)

    def test_point_refinement_improves_iou(self):
        initial_iou = 0.75
        self.segmenter.default_mock_iou = initial_iou
        masks = self.segmenter.segment_boxes(self.image, self.boxes)
        initial_mask = masks[0]

        corrective_pt = (125, 125, True)
        refined = self.segmenter.refine_with_point(
            self.image, self.boxes[0], initial_mask.mask_array, corrective_pt
        )
        self.assertGreater(refined.predicted_iou, initial_iou)


class TestRefinementHeuristic(unittest.TestCase):
    """Test suite for IoU calculation and error centroid geometry."""

    def test_should_refine(self):
        self.assertTrue(should_refine(0.84, threshold=0.85))
        self.assertFalse(should_refine(0.85, threshold=0.85))
        self.assertFalse(should_refine(0.92, threshold=0.85))

    def test_compute_error_centroid_under_segmentation(self):
        # Create empty mask where bounding box expected something
        mask = np.zeros((100, 100), dtype=bool)
        box = (20.0, 20.0, 80.0, 80.0)

        cx, cy, is_positive = compute_error_centroid(mask, box)
        self.assertTrue(is_positive)
        self.assertTrue(20 <= cx <= 80)
        self.assertTrue(20 <= cy <= 80)


class TestVisionWorkflowRunner(unittest.TestCase):
    """Integration test suite for the complete System-1 execution graph."""

    def setUp(self):
        self.runner = VisionWorkflowRunner(mock_mode=True, iou_threshold=0.85)
        self.image = Image.new("RGB", (640, 480), color=(100, 150, 70))

    def test_end_to_end_execution(self):
        initial_state = create_initial_state(self.image, text_prompt="cotton weed . broadleaf .")
        final_state = self.runner.run(initial_state)

        # Assert detections and segmentations are present
        self.assertGreater(len(final_state["boxes"]), 0)
        self.assertGreater(len(final_state["masks"]), 0)

        # Assert spray map computed
        spray_map = final_state.get("spray_map")
        self.assertIsNotNone(spray_map)
        self.assertIn("infestation_percentage", spray_map)
        self.assertIn("chemical_savings_percentage", spray_map)
        self.assertGreater(spray_map["chemical_savings_percentage"], 50.0)

        # Assert artifact created
        self.assertIn("spray_map", final_state["artifacts"])


if __name__ == "__main__":
    unittest.main()
