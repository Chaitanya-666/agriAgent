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


class TestPlantRulesInTheGate(unittest.TestCase):
    """The workflow's gate with plant_rules on, and the GeoJSON export of what it finds."""

    def run_gate(self, plant_rules):
        from PIL import Image

        from app.components.pipeline import build_spray_geojson
        from src.workflow import VisionWorkflowRunner

        image = field()
        image[20:80, 20:80] = GREEN  # crop plant found by the detector
        image[150:159, 150:159] = GREEN  # small weed the detector never boxed (81 px)
        crop = np.zeros((200, 200), dtype=bool)
        crop[15:85, 15:85] = True
        box = {
            "x1": 15.0,
            "y1": 15.0,
            "x2": 85.0,
            "y2": 85.0,
            "label": "sugar beet plant",
            "score": 0.6,
        }
        state = {
            "image": Image.fromarray(image),
            "masks": [
                {"label": "sugar beet plant", "mask_array": crop, "predicted_iou": 0.95, "box": box}
            ],
            "text_prompt": "weed . sugar beet plant .",
        }
        out = VisionWorkflowRunner(mock_mode=True, plant_rules=plant_rules).spray_map_node(state)
        composite = out["artifacts"]["spray_map"].payload["composite_mask"]
        return out, composite, build_spray_geojson({**state, **out})

    def test_small_weed_is_sprayed_and_crop_is_not(self):
        out, composite, geojson = self.run_gate(plant_rules=True)
        self.assertTrue(composite[155, 155])
        self.assertFalse(composite[50, 50])
        self.assertEqual(out["spray_map"]["plant_rules"]["weed"], 1)
        # An 81-pixel weed must survive the GeoJSON fragment filter.
        self.assertEqual(len(geojson["features"]), 1)

    def test_switch_off_keeps_the_old_behaviour(self):
        out, composite, _ = self.run_gate(plant_rules=False)
        self.assertFalse(composite.any())
        self.assertEqual(out["spray_map"]["plant_rules"], {})
