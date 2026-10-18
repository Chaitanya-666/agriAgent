"""
tests/test_crop_protection.py
Crop-protection metrics on hand-checkable inputs.

The three 5 x 5 grids are the ones in docs/AgriAgent_Team_Tasks.pdf, task SA-2, so a person's
hand computation checks the code independently.
"""

import sys
import unittest
from unittest import mock

import numpy as np

from src.evaluation.crop_protection import (
    ground_truth_masks,
    otsu_threshold,
    spray_metrics,
    vegetation_mask,
)
from src.evaluation.iou_dice import compute_herbicide_savings, spray_footprint


def grid(rows):
    """Turn rows like 'C C . W .' into crop and weed masks, or '1 0 0 1 0' into a spray mask."""
    cells = [row.split() for row in rows]
    crop = np.array([[c == "C" for c in row] for row in cells])
    weed = np.array([[c == "W" for c in row] for row in cells])
    sprayed = np.array([[c == "1" for c in row] for row in cells])
    return crop, weed, sprayed


class TestSA2Examples(unittest.TestCase):
    def check(self, truth, spray, crop_pct, recall_pct, savings_pct):
        crop, weed, _ = grid(truth)
        _, _, sprayed = grid(spray)
        m = spray_metrics(sprayed, crop, weed)
        self.assertEqual(m["crop_sprayed_pct"], crop_pct)
        self.assertEqual(m["weed_recall_pct"], recall_pct)
        self.assertEqual(m["savings_pct"], savings_pct)

    def test_example_a_partial_spray(self):
        self.check(
            ["C C . . .", "C C . W .", ". . . W W", ". . . . .", "W . . C C"],
            ["1 0 0 0 0", "0 0 0 1 0", "0 0 0 1 1", "0 0 0 0 0", "0 0 0 1 0"],
            crop_pct=33.33,  # 2 of 6 crop pixels sprayed
            recall_pct=75.0,  # 3 of 4 weed pixels sprayed
            savings_pct=80.0,  # 5 of 25 pixels sprayed
        )

    def test_example_b_nothing_sprayed(self):
        self.check(
            [". C C . .", ". C C . .", ". . . . W", "W . . . .", ". . . . ."],
            ["0 0 0 0 0"] * 5,
            crop_pct=0.0,
            recall_pct=0.0,
            savings_pct=100.0,
        )

    def test_example_c_everything_sprayed(self):
        self.check(
            ["C . . . W", "C . . . W", ". . W . .", ". . . . .", ". C . . ."],
            ["1 1 1 1 1"] * 5,
            crop_pct=100.0,
            recall_pct=100.0,
            savings_pct=0.0,
        )

    def test_missing_category_gives_none_not_zero(self):
        sprayed = np.zeros((4, 4), dtype=bool)
        m = spray_metrics(sprayed, np.zeros((4, 4), bool), np.zeros((4, 4), bool))
        self.assertIsNone(m["crop_sprayed_pct"])
        self.assertIsNone(m["weed_recall_pct"])


class TestGroundTruthFromBoxes(unittest.TestCase):
    def test_only_vegetation_inside_boxes_counts(self):
        vegetation = np.zeros((10, 10), dtype=bool)
        vegetation[2:4, 2:4] = True  # a plant inside the crop box
        vegetation[8, 8] = True  # vegetation outside every box
        annotations = [{"category": "crop", "box": [0, 0, 5, 5]}]
        crop, weed, crop_objects, weed_objects = ground_truth_masks(annotations, vegetation)
        self.assertEqual(int(crop.sum()), 4)
        self.assertEqual(int(weed.sum()), 0)
        self.assertEqual((len(crop_objects), len(weed_objects)), (1, 0))

    def test_overlap_counts_as_crop(self):
        vegetation = np.ones((10, 10), dtype=bool)
        annotations = [
            {"category": "crop", "box": [0, 0, 6, 6]},
            {"category": "weed", "box": [4, 4, 8, 8]},
        ]
        crop, weed, _, _ = ground_truth_masks(annotations, vegetation)
        self.assertFalse((crop & weed).any())
        self.assertEqual(int(weed.sum()), 16 - 4)

    def test_object_counts(self):
        vegetation = np.ones((10, 10), dtype=bool)
        annotations = [
            {"category": "crop", "box": [0, 0, 2, 2]},
            {"category": "weed", "box": [5, 5, 7, 7]},
            {"category": "weed", "box": [8, 0, 10, 2]},
        ]
        crop, weed, crop_objects, weed_objects = ground_truth_masks(annotations, vegetation)
        sprayed = np.zeros((10, 10), dtype=bool)
        sprayed[0, 0] = True  # one crop pixel
        sprayed[5:7, 5:7] = True  # all of the first weed
        m = spray_metrics(sprayed, crop, weed, crop_objects, weed_objects)
        self.assertEqual((m["crop_plants"], m["crop_plants_damaged"]), (1, 1))
        self.assertEqual((m["weed_plants"], m["weed_plants_hit"]), (2, 1))


class TestVegetationMask(unittest.TestCase):
    def test_green_plant_on_brown_soil(self):
        image = np.full((40, 40, 3), (120, 95, 65), dtype=np.uint8)
        image[10:20, 10:20] = (60, 170, 50)
        mask = vegetation_mask(image)
        self.assertEqual(int(mask.sum()), 100)
        self.assertTrue(mask[15, 15])

    def test_otsu_splits_two_groups(self):
        values = np.concatenate([np.full(100, 10.0), np.full(100, 90.0)])
        self.assertTrue(10 < otsu_threshold(values) < 90)


class TestSprayFootprint(unittest.TestCase):
    """Known issue K10: the buffer must not depend on whether OpenCV is installed."""

    def setUp(self):
        self.mask = np.zeros((30, 30), dtype=bool)
        self.mask[10:12, 15] = True

    def test_buffer_grows_each_side_by_buffer_pixels(self):
        grown = spray_footprint(self.mask, buffer_pixels=3)
        self.assertEqual(int(grown.sum()), (2 + 6) * (1 + 6))

    def test_same_result_without_opencv(self):
        with_cv2 = spray_footprint(self.mask, buffer_pixels=4)
        with mock.patch.dict(sys.modules, {"cv2": None}):
            without_cv2 = spray_footprint(self.mask, buffer_pixels=4)
            savings_without = compute_herbicide_savings(self.mask, (30, 30), buffer_pixels=4)
        np.testing.assert_array_equal(with_cv2, without_cv2)
        self.assertEqual(
            compute_herbicide_savings(self.mask, (30, 30), buffer_pixels=4), savings_without
        )


if __name__ == "__main__":
    unittest.main()
