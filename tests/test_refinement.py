"""
tests/test_refinement.py
Unit and boundary test suite for morphological contour/gradient refinement,
negative soil prompt points, coordinate normalization, and image boundary invariants.
"""

import unittest
import numpy as np
from PIL import Image

from src.vision.refinement import (
    binary_closing,
    binary_dilation,
    binary_erosion,
    binary_opening,
    compute_error_centroid,
    generate_refinement_points,
    get_negative_prompt_points,
    get_refinement_point,
    morphological_gradient,
    normalize_box_coordinates,
    should_refine,
)


class TestCoordinateNormalization(unittest.TestCase):
    """Tests defensive bounding box coordinate normalization."""

    def setUp(self):
        self.shape = (100, 120)  # height=100, width=120

    def test_standard_coordinates(self):
        box = (10.0, 20.0, 50.0, 60.0)
        norm = normalize_box_coordinates(box, self.shape)
        self.assertEqual(norm, (10, 20, 50, 60))

    def test_inverted_coordinates_ordered_correctly(self):
        """Inverted coords (x1 > x2 or y1 > y2) must be normalized so xmin <= xmax, ymin <= ymax."""
        box = (80.0, 90.0, 20.0, 30.0)
        norm = normalize_box_coordinates(box, self.shape)
        self.assertEqual(norm, (20, 30, 80, 90))

    def test_float_rounding(self):
        box = (10.4, 20.6, 49.8, 60.2)
        norm = normalize_box_coordinates(box, self.shape)
        self.assertEqual(norm, (10, 21, 50, 60))

    def test_out_of_bounds_negative_clamped(self):
        box = (-15.0, -25.0, 50.0, 60.0)
        norm = normalize_box_coordinates(box, self.shape)
        self.assertEqual(norm, (0, 0, 50, 60))

    def test_out_of_bounds_exceeding_dimensions_clamped(self):
        box = (10.0, 20.0, 200.0, 150.0)
        norm = normalize_box_coordinates(box, self.shape)
        self.assertEqual(norm, (10, 20, 120, 100))

    def test_degenerate_zero_area_box(self):
        box = (40.0, 40.0, 40.0, 40.0)
        norm = normalize_box_coordinates(box, self.shape)
        self.assertEqual(norm, (40, 40, 40, 40))


class TestMorphologicalPrimitives(unittest.TestCase):
    """Tests pure NumPy morphological operators."""

    def test_dilation_expands_mask(self):
        mask = np.zeros((20, 20), dtype=bool)
        mask[10, 10] = True
        dilated = binary_dilation(mask, radius=1)
        self.assertTrue(dilated[10, 10])
        self.assertTrue(dilated[9, 10])
        self.assertTrue(dilated[11, 10])
        self.assertTrue(dilated[10, 9])
        self.assertTrue(dilated[10, 11])
        self.assertEqual(dilated.sum(), 9)  # 3x3 square

    def test_erosion_shrinks_mask(self):
        mask = np.zeros((20, 20), dtype=bool)
        mask[8:13, 8:13] = True  # 5x5 square
        eroded = binary_erosion(mask, radius=1)
        self.assertEqual(eroded.sum(), 9)  # shrinks to 3x3
        self.assertTrue(eroded[10, 10])
        self.assertFalse(eroded[8, 8])

    def test_closing_fills_internal_holes(self):
        mask = np.ones((15, 15), dtype=bool)
        mask[7, 7] = False  # single-pixel internal hole
        closed = binary_closing(mask, radius=2)
        self.assertTrue(closed[7, 7], "Closing should fill small internal hole.")

    def test_opening_removes_thin_spurious_noise(self):
        mask = np.zeros((20, 20), dtype=bool)
        mask[5:15, 5:15] = True  # main body
        mask[1, 1] = True        # isolated noise pixel
        mask[18, 18] = True      # isolated noise pixel
        opened = binary_opening(mask, radius=1)
        self.assertFalse(opened[1, 1], "Opening should remove isolated noise.")
        self.assertFalse(opened[18, 18])
        self.assertTrue(opened[10, 10], "Main body should be preserved.")

    def test_morphological_gradient_boundary_ring(self):
        mask = np.zeros((20, 20), dtype=bool)
        mask[5:15, 5:15] = True  # 10x10 square
        grad = morphological_gradient(mask, radius=1)
        # Center should not be in the boundary ring
        self.assertFalse(grad[10, 10])
        # Ring pixels around perimeter should be active
        self.assertTrue(grad[4, 10])
        self.assertTrue(grad[5, 10])


class TestMorphologicalRefinementHeuristic(unittest.TestCase):
    """Tests morphological contour refinement and error centroid calculation."""

    def test_empty_mask_under_segmentation(self):
        """Empty mask in bounding box must yield under-segmentation positive prompt inside box."""
        mask = np.zeros((100, 100), dtype=bool)
        box = (20.0, 20.0, 80.0, 80.0)
        cx, cy, is_positive = compute_error_centroid(mask, box)
        self.assertTrue(is_positive, "Empty mask must trigger under-segmentation.")
        self.assertTrue(20 <= cx <= 80)
        self.assertTrue(20 <= cy <= 80)

    def test_internal_canopy_hole_prompts_positive_point(self):
        """Internal hole in foliage canopy contour must be targeted with positive point."""
        mask = np.zeros((100, 100), dtype=bool)
        mask[30:70, 30:70] = True
        mask[48:52, 48:52] = False  # 4x4 hole in canopy
        box = (25.0, 25.0, 75.0, 75.0)

        cx, cy, is_positive = compute_error_centroid(mask, box)
        self.assertTrue(is_positive)
        self.assertTrue(45 <= cx <= 55)
        self.assertTrue(45 <= cy <= 55)

    def test_over_segmentation_spillover_prompts_negative_point(self):
        """Mask spilling outside detection bounding box must trigger negative corrective point."""
        mask = np.zeros((100, 100), dtype=bool)
        mask[30:70, 30:70] = True
        # Leak outside the box:
        mask[5:20, 30:70] = True  # large leak above box
        box = (30.0, 30.0, 70.0, 70.0)

        cx, cy, is_positive = compute_error_centroid(mask, box)
        self.assertFalse(is_positive, "Over-segmentation outside box must prompt negative point.")
        self.assertTrue(cy < 30, "Corrective point should target the leaked region outside box.")

    def test_image_guided_refinement_excess_green(self):
        """When RGB image is provided, contour points with high green vegetation index are prioritized."""
        h, w = 100, 100
        mask = np.zeros((h, w), dtype=bool)
        mask[40:60, 40:60] = True  # current partial mask
        box = (20.0, 20.0, 80.0, 80.0)

        # Create image with soil background (brown: R=150, G=100, B=60)
        img_arr = np.full((h, w, 3), [150, 100, 60], dtype=np.uint8)
        # Add real foliage patch adjacent to mask on the right (bright green: R=40, G=190, B=30)
        img_arr[40:60, 60:75] = [40, 190, 30]

        cx, cy, is_positive = compute_error_centroid(mask, box, image=img_arr)
        self.assertTrue(is_positive)
        self.assertTrue(cx >= 60, "Centroid should weight toward high Excess Green foliage region.")


class TestNegativeSoilPromptPoints(unittest.TestCase):
    """Tests background soil negative prompt point generation."""

    def test_negative_points_outside_foliage_perimeter(self):
        """Negative prompt points must lie in background soil safely outside dilated foliage."""
        h, w = 100, 100
        mask = np.zeros((h, w), dtype=bool)
        mask[40:60, 40:60] = True  # centered foliage
        box = (20.0, 20.0, 80.0, 80.0)

        neg_points = get_negative_prompt_points(mask, box, count=3)
        self.assertEqual(len(neg_points), 3)

        for px, py, is_pos in neg_points:
            self.assertFalse(is_pos, "Negative prompt point must have is_positive=False")
            self.assertFalse(mask[py, px], "Negative prompt point must not lie on foliage mask")
            self.assertTrue(0 <= px < w)
            self.assertTrue(0 <= py < h)

    def test_soil_preference_with_image(self):
        """Prefers background pixels that exhibit soil characteristics (low ExG)."""
        h, w = 100, 100
        mask = np.zeros((h, w), dtype=bool)
        mask[40:60, 40:60] = True
        box = (20.0, 20.0, 80.0, 80.0)

        img_arr = np.full((h, w, 3), [140, 90, 50], dtype=np.uint8)  # soil
        neg_points = get_negative_prompt_points(mask, box, count=2, image=img_arr)
        self.assertEqual(len(neg_points), 2)
        for px, py, is_pos in neg_points:
            self.assertFalse(is_pos)


class TestImageBoundaryInvariants(unittest.TestCase):
    """Tests extreme and boundary cases to guarantee no IndexError or crash."""

    def test_random_and_extreme_boxes(self):
        h, w = 80, 80
        mask = np.zeros((h, w), dtype=bool)
        mask[30:50, 30:50] = True

        extreme_boxes = [
            (-50.0, -50.0, -10.0, -10.0),      # completely outside top-left
            (100.0, 100.0, 200.0, 200.0),      # completely outside bottom-right
            (0.0, 0.0, 0.0, 0.0),              # zero area at origin
            (79.0, 79.0, 79.0, 79.0),          # zero area at boundary
            (70.0, 20.0, 10.0, 60.0),          # reversed x coords
            (20.0, 70.0, 60.0, 10.0),          # reversed y coords
            (0.0, 0.0, 80.0, 80.0),            # full image
        ]

        for box in extreme_boxes:
            cx, cy, _ = compute_error_centroid(mask, box)
            self.assertTrue(0 <= cx < w, f"cx={cx} out of bounds for box {box}")
            self.assertTrue(0 <= cy < h, f"cy={cy} out of bounds for box {box}")

            neg_pts = get_negative_prompt_points(mask, box, count=2)
            for nx, ny, _ in neg_pts:
                self.assertTrue(0 <= nx < w, f"nx={nx} out of bounds for box {box}")
                self.assertTrue(0 <= ny < h, f"ny={ny} out of bounds for box {box}")

    def test_refinement_gating_functions(self):
        self.assertTrue(should_refine(0.70, threshold=0.85))
        self.assertFalse(should_refine(0.85, threshold=0.85))
        self.assertFalse(should_refine(0.99, threshold=0.85))

        mask = np.zeros((50, 50), dtype=bool)
        box = (10.0, 10.0, 40.0, 40.0)

        # High IoU returns None (no refinement needed)
        self.assertIsNone(get_refinement_point(mask, box, predicted_iou=0.92, threshold=0.85))

        # Low IoU returns corrective point
        pt = get_refinement_point(mask, box, predicted_iou=0.75, threshold=0.85)
        self.assertIsNotNone(pt)
        self.assertEqual(len(pt), 3)

    def test_generate_refinement_points_paired(self):
        mask = np.zeros((60, 60), dtype=bool)
        mask[20:40, 20:40] = True
        box = (10.0, 10.0, 50.0, 50.0)

        res = generate_refinement_points(mask, box, predicted_iou=0.72, threshold=0.85, num_negative=2)
        self.assertTrue(res["needs_refine"])
        self.assertGreater(len(res["all_points"]), 0)
        self.assertGreater(len(res["negative_points"]), 0)


if __name__ == "__main__":
    unittest.main()
