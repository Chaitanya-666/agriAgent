"""
tests/test_visualization.py
Unit tests for visualization utilities (masks and bounding box overlays).
"""

import unittest
import numpy as np
from PIL import Image

from src.vision.visualization import (
    COLOR_CROP,
    COLOR_DISEASE,
    COLOR_WEED,
    draw_boxes,
    get_label_color,
    overlay_masks,
)
from src.state import Box, Mask


class TestVisualization(unittest.TestCase):
    """Test suite for mask overlay compositing and bounding box rendering."""

    def setUp(self):
        # Create a simple test RGB image (64x64)
        self.img = Image.new("RGB", (64, 64), color=(120, 100, 80))

    def test_get_label_color(self):
        """Verify semantic label mapping to RGB color codes."""
        self.assertEqual(get_label_color("cotton weed"), COLOR_WEED)
        self.assertEqual(get_label_color("weed"), COLOR_WEED)
        self.assertEqual(get_label_color("cotton crop"), COLOR_CROP)
        self.assertEqual(get_label_color("plant"), COLOR_CROP)
        self.assertEqual(get_label_color("leaf disease"), COLOR_DISEASE)
        self.assertEqual(get_label_color("fungal blight"), COLOR_DISEASE)
        self.assertEqual(get_label_color("pest"), COLOR_DISEASE)

    def test_draw_boxes_empty(self):
        """Empty box list returns an identical copy of image."""
        result = draw_boxes(self.img, [])
        self.assertEqual(result.size, self.img.size)
        self.assertEqual(result.mode, "RGB")

    def test_draw_boxes_renders_annotations(self):
        """Bounding boxes are rendered without altering image dimensions."""
        boxes: list[Box] = [
            {"x1": 10.0, "y1": 10.0, "x2": 30.0, "y2": 30.0, "label": "weed", "score": 0.92},
            {"x1": 35.0, "y1": 35.0, "x2": 55.0, "y2": 55.0, "label": "crop", "score": 0.88},
        ]
        result = draw_boxes(self.img, boxes)
        self.assertEqual(result.size, (64, 64))
        self.assertEqual(result.mode, "RGB")
        # Ensure pixels have been modified by drawing
        orig_arr = np.array(self.img)
        res_arr = np.array(result)
        self.assertFalse(np.array_equal(orig_arr, res_arr))

    def test_overlay_masks_empty(self):
        """Empty mask list returns identical copy of image."""
        result = overlay_masks(self.img, [])
        self.assertEqual(result.size, self.img.size)
        self.assertEqual(result.mode, "RGB")

    def test_overlay_masks_compositing(self):
        """Mask overlay applies semi-transparent coloration accurately."""
        mask_arr = np.zeros((64, 64), dtype=bool)
        mask_arr[15:35, 15:35] = True

        masks: list[Mask] = [
            {
                "mask_array": mask_arr,
                "predicted_iou": 0.95,
                "box": {"x1": 15, "y1": 15, "x2": 35, "y2": 35, "label": "weed", "score": 0.9},
                "label": "weed",
            }
        ]

        result = overlay_masks(self.img, masks, alpha=0.5)
        self.assertEqual(result.size, (64, 64))
        self.assertEqual(result.mode, "RGB")

        orig_arr = np.array(self.img)
        res_arr = np.array(result)
        # Background pixels outside the mask must remain untouched
        self.assertTrue(np.array_equal(orig_arr[0:10, 0:10], res_arr[0:10, 0:10]))
        # Pixels inside the mask must be blended
        self.assertFalse(np.array_equal(orig_arr[15:35, 15:35], res_arr[15:35, 15:35]))

    def test_overlay_masks_handles_mismatched_dimensions(self):
        """Gracefully ignores masks with incorrect dimensions instead of crashing."""
        invalid_mask = np.zeros((32, 32), dtype=bool)
        masks: list[Mask] = [
            {
                "mask_array": invalid_mask,
                "predicted_iou": 0.5,
                "box": {"x1": 0, "y1": 0, "x2": 10, "y2": 10, "label": "weed", "score": 0.5},
                "label": "weed",
            }
        ]
        result = overlay_masks(self.img, masks)
        self.assertEqual(result.size, self.img.size)


if __name__ == "__main__":
    unittest.main()
