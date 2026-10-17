"""
tests/test_vision_pipeline.py
Unit and Integration Tests for AgriAgent System-1 Vision Pipeline.

Verifies:
1. Grounding DINO zero-shot detection and box coordinate contracts.
2. SAM 2 instance segmentation and mask format validation.
3. Active closed-loop IoU refinement with error centroid calculation.
4. End-to-end VisionWorkflowRunner state transitions and herbicide savings calculations.
"""

import contextlib
import sys
from types import SimpleNamespace
import unittest
from unittest import mock
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
        detections = self.engine.detect(self.image, text_prompt="weed . broadleaf weed .")
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


class _FakeTensor:
    """Just enough of a torch tensor for the Hugging Face SAM 2 code path."""

    def __init__(self, array):
        self.array = np.asarray(array)

    def __getitem__(self, index):
        return _FakeTensor(self.array[index])

    def cpu(self):
        return self

    def numpy(self):
        return self.array

    def item(self):
        return self.array.item()


class _FakeBatch(dict):
    def to(self, device):
        return self


class _FakeSam2Processor:
    def __init__(self):
        self.prompts = []

    def __call__(self, images=None, return_tensors=None, **prompts):
        self.prompts.append(prompts)
        height, width = images.size[1], images.size[0]
        return _FakeBatch(pixel_values=_FakeTensor(0), original_sizes=[(height, width)], **prompts)

    def post_process_masks(self, masks, original_sizes):
        # transformers 5.x signature: there is no reshaped_input_sizes argument (issue #13).
        height, width = original_sizes[0]
        mask = np.zeros((1, 1, height, width), dtype=bool)
        mask[0, 0, 10:20, 10:30] = True
        return [_FakeTensor(mask)]


class _FakeSam2Model:
    def __init__(self):
        self.kwargs = {}

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            pred_masks=_FakeTensor(np.zeros((1, 1, 1, 4, 4))),
            iou_scores=_FakeTensor([[[0.62]]]),
        )


class TestSAM2HuggingFaceBackend(unittest.TestCase):
    """The live transformers path, with the model and processor faked so no weights are needed."""

    def setUp(self):
        self.segmenter = SAM2Segmenter(mock_mode=True)
        self.segmenter.mock_mode = False
        self.segmenter.device = "cpu"
        self.segmenter._processor = _FakeSam2Processor()
        self.segmenter._model = _FakeSam2Model()
        self.image = Image.new("RGB", (64, 48))
        self.box: Box = {"x1": 5.0, "y1": 5.0, "x2": 40.0, "y2": 30.0, "label": "weed", "score": 0.7}
        self.fake_torch = mock.patch.dict(
            sys.modules, {"torch": SimpleNamespace(no_grad=contextlib.nullcontext)}
        )
        self.fake_torch.start()
        self.addCleanup(self.fake_torch.stop)

    def test_segment_boxes_returns_model_score_and_single_mask(self):
        seg = self.segmenter.segment_boxes(self.image, [self.box])[0]
        self.assertEqual(seg.mask_array.shape, (48, 64))
        self.assertEqual(seg.area_pixels, 200)
        self.assertAlmostEqual(seg.predicted_iou, 0.62)
        self.assertFalse(self.segmenter._model.kwargs["multimask_output"])

    def test_refine_with_point_sends_point_prompt(self):
        refined = self.segmenter.refine_with_point(
            self.image, self.box, np.zeros((48, 64), dtype=bool), (15, 12, False)
        )
        prompts = self.segmenter._processor.prompts[-1]
        self.assertEqual(prompts["input_points"], [[[[15, 12]]]])
        self.assertEqual(prompts["input_labels"], [[[0]]])
        self.assertAlmostEqual(refined.predicted_iou, 0.62)


class TestRealModeFailsLoudly(unittest.TestCase):
    """Known issue K5: real mode must never fall back to mock output silently."""

    def test_detector_raises_when_model_cannot_load(self):
        with mock.patch.dict(sys.modules, {"torch": None}):
            with self.assertRaisesRegex(RuntimeError, "Real mode requested but Grounding DINO"):
                GroundingDINOEngine(mock_mode=False)

    def test_segmenter_raises_when_model_cannot_load(self):
        with mock.patch.dict(sys.modules, {"torch": None}):
            with self.assertRaisesRegex(RuntimeError, "Real mode requested but SAM 2"):
                SAM2Segmenter(mock_mode=False)


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
        initial_state = create_initial_state(self.image, text_prompt="weed . broadleaf weed .")
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

    def test_system2_failure_keeps_vision_results(self):
        failing_system2 = mock.Mock()
        failing_system2.system2_node.side_effect = RuntimeError("provider unreachable")
        runner = VisionWorkflowRunner(mock_mode=True, system2=failing_system2)
        state = create_initial_state(self.image, text_prompt="weed .")
        state["system2_needed"] = True

        out = runner.system2_node(state)

        self.assertEqual(out["system2_error"], "provider unreachable")
        self.assertIsNone(out["prescription_report"])


if __name__ == "__main__":
    unittest.main()
