"""
tests/test_metrics.py
Unit tests for segmentation evaluation metrics and herbicide savings calculation.
"""

import unittest
import numpy as np

from src.evaluation.iou_dice import (
    compute_iou,
    compute_dice,
    evaluate_batch,
    compute_herbicide_savings,
)


class TestMetrics(unittest.TestCase):
    """Test suite for IoU, Dice coefficient, and precision spot-spray volume metrics."""

    def test_compute_iou_identical(self):
        """Identical masks must yield an IoU of exactly 1.0."""
        mask = np.zeros((20, 20), dtype=bool)
        mask[5:15, 5:15] = True
        self.assertAlmostEqual(compute_iou(mask, mask), 1.0, places=4)

    def test_compute_iou_disjoint(self):
        """Completely disjoint masks must yield an IoU of 0.0."""
        mask1 = np.zeros((20, 20), dtype=bool)
        mask1[0:5, 0:5] = True
        mask2 = np.zeros((20, 20), dtype=bool)
        mask2[10:15, 10:15] = True
        self.assertAlmostEqual(compute_iou(mask1, mask2), 0.0, places=4)

    def test_compute_iou_partial_overlap(self):
        """Overlap of 50% intersection over union computes correctly."""
        mask1 = np.zeros((10, 10), dtype=bool)
        mask1[:10, :5] = True  # 50 pixels
        mask2 = np.zeros((10, 10), dtype=bool)
        mask2[:10, 2:7] = True  # 50 pixels, overlap is 30 pixels, union is 70 pixels
        expected_iou = 30.0 / 70.0
        self.assertAlmostEqual(compute_iou(mask1, mask2), expected_iou, places=4)

    def test_compute_dice_identical(self):
        """Identical masks yield a Dice coefficient of 1.0."""
        mask = np.zeros((10, 10), dtype=bool)
        mask[2:8, 2:8] = True
        self.assertAlmostEqual(compute_dice(mask, mask), 1.0, places=4)

    def test_evaluate_batch(self):
        """Batch evaluation computes mean and std metrics properly."""
        m1 = np.ones((5, 5), dtype=bool)
        m2 = np.ones((5, 5), dtype=bool)
        results = evaluate_batch([m1, m1], [m2, m2])
        self.assertEqual(results["num_samples"], 2)
        self.assertAlmostEqual(results["mean_iou"], 1.0, places=4)
        self.assertAlmostEqual(results["mean_dice"], 1.0, places=4)

    def test_compute_herbicide_savings(self):
        """Weed mask covering 10% of field should yield significant chemical savings."""
        total_shape = (100, 100)
        weed_mask = np.zeros(total_shape, dtype=bool)
        # 10x10 weed patch in the center = 100 pixels out of 10000 pixels (1%)
        weed_mask[45:55, 45:55] = True

        savings = compute_herbicide_savings(weed_mask, total_shape, buffer_pixels=2)
        # Even with dilation buffer, savings should be > 85%
        self.assertGreater(savings, 85.0)
        self.assertLessEqual(savings, 100.0)


if __name__ == "__main__":
    unittest.main()
