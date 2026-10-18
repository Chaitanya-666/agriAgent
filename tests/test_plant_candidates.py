"""
tests/test_plant_candidates.py
Rule-based classification of every green patch (src/vision/plant_candidates.py).
"""

import sys
import unittest
from unittest import mock

import numpy as np

from src.vision.plant_candidates import classify_plants, close_gaps, connected_components

SOIL = (120, 95, 65)
GREEN = (60, 170, 50)


def field(size=200):
    return np.full((size, size, 3), SOIL, dtype=np.uint8)


class TestComponents(unittest.TestCase):
    def test_python_fallback_matches_opencv(self):
        mask = np.zeros((20, 20), dtype=bool)
        mask[2:5, 2:5] = True
        mask[10:12, 10:15] = True
        mask[6, 6] = True  # touches the first block diagonally
        with_cv2 = connected_components(mask)[1]
        with mock.patch.dict(sys.modules, {"cv2": None}):
            labels, count = connected_components(mask)
        self.assertEqual(count, 3 if with_cv2 == 3 else with_cv2)
        self.assertEqual(labels[2, 2], labels[4, 4])

    def test_close_gaps_joins_nearby_leaves(self):
        mask = np.zeros((20, 20), dtype=bool)
        mask[5:10, 5:8] = True
        mask[5:10, 9:12] = True  # one empty column between two leaves
        self.assertEqual(connected_components(close_gaps(mask, 1))[1], 1)


class TestRules(unittest.TestCase):
    def test_patch_inside_crop_mask_is_crop(self):
        image = field()
        image[50:80, 50:80] = GREEN
        crop_mask = np.zeros((200, 200), dtype=bool)
        crop_mask[45:85, 45:85] = True
        weed, crop, patches = classify_plants(image, [crop_mask])
        self.assertFalse(weed.any())
        self.assertEqual(patches[0]["verdict"], "crop")

    def test_small_patch_beside_large_crop_is_weed(self):
        image = field()
        image[20:80, 20:80] = GREEN  # crop plant, 3600 px
        image[150:160, 150:160] = GREEN  # small plant, 100 px
        crop_mask = np.zeros((200, 200), dtype=bool)
        crop_mask[15:85, 15:85] = True
        weed, crop, _ = classify_plants(image, [crop_mask])
        self.assertTrue(weed[155, 155])
        self.assertFalse(weed[50, 50])

    def test_rows_protect_plants_on_the_row(self):
        image = field()
        for x in range(10, 190, 40):  # a horizontal crop row at y 90-110
            image[90:110, x : x + 20] = GREEN
        image[20:28, 100:108] = GREEN  # off the row
        image[95:103, 135:143] = GREEN  # small, but inside the row band
        weed, crop, _ = classify_plants(image, [])
        self.assertTrue(weed[24, 104])
        self.assertFalse(weed[99, 139])

    def test_lone_plant_without_reference_is_never_sprayed(self):
        # Known limitation (v3, frozen after the held-out test): a single plant forms a strong
        # "row" band and is protected as crop rather than marked unsure. Either way it is safe.
        image = field()
        image[90:100, 90:100] = GREEN
        weed, crop, patches = classify_plants(image, [])
        self.assertFalse(weed.any())
        self.assertNotEqual(patches[0]["verdict"], "weed")


if __name__ == "__main__":
    unittest.main()
