"""Regression tests for the approved-mask spray/export contract."""

import unittest

import numpy as np

from app.components.pipeline import build_spray_geojson
from src.state import Artifact, ArtifactType
from src.workflow import VisionWorkflowRunner


class SprayExportSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = VisionWorkflowRunner(mock_mode=True)

    def _mask(self, label: str, fill: float = 0.05, score: float = 0.9, iou: float = 0.95):
        pixels = np.zeros((480, 640), dtype=bool)
        pixels[: int(480 * fill), :640] = True
        return {"label": label, "mask_array": pixels, "predicted_iou": iou, "box": {"score": score}}

    def _features(self, workflow_output, boxes=None):
        return build_spray_geojson(
            {
                "spray_map": workflow_output["spray_map"],
                "artifacts": workflow_output["artifacts"],
                "boxes": boxes or [],
            }
        )["features"]

    def test_crop_labels_never_produce_spray_features(self):
        for label in ("crop", "cotton", "sugarbeet", "beet"):
            with self.subTest(label=label):
                output = self.runner.spray_map_node({"masks": [self._mask(label)]})
                self.assertEqual(self._features(output), [])

    def test_labels_containing_crop_names_never_produce_features(self):
        for label in ("cropweed", "cotton_weed", "sugarbeet weed", "beet-weed"):
            with self.subTest(label=label):
                output = self.runner.spray_map_node({"masks": [self._mask(label)]})
                self.assertEqual(self._features(output), [])

    def test_approved_weed_labels_produce_features(self):
        output = self.runner.spray_map_node({"masks": [self._mask("broadleaf_weed")]})
        self.assertEqual(len(self._features(output)), 1)

    def test_recognized_grass_label_is_consistent(self):
        output = self.runner.spray_map_node({"masks": [self._mask("grass")]})
        features = self._features(output)
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["properties"]["target"], "grass")

    def test_high_infestation_suppresses_spray(self):
        # Two separate weed masks of 45% each: no single plant is too large, together 90%.
        top, bottom = self._mask("weed", fill=0.45), self._mask("weed", fill=0.45)
        bottom["mask_array"] = np.flipud(bottom["mask_array"]).copy()
        output = self.runner.spray_map_node({"masks": [top, bottom]})
        self.assertEqual(output["spray_map"]["safety_action"], "SUPPRESS_SPRAY")
        self.assertFalse(output["spray_map"]["spray_allowed"])
        self.assertEqual(self._features(output), [])

    def test_low_confidence_weed_is_withheld(self):
        # Known issue K1: the gate used to be called with confidence 1.0 for every mask.
        output = self.runner.spray_map_node({"masks": [self._mask("weed", score=0.5)]})
        self.assertEqual(self._features(output), [])
        self.assertIn(
            "Low detection confidence", output["spray_map"]["withheld_masks"][0]["reason"]
        )

    def test_poor_quality_mask_is_withheld(self):
        output = self.runner.spray_map_node({"masks": [self._mask("weed", iou=0.6)]})
        self.assertEqual(self._features(output), [])

    def test_mask_without_confidence_is_withheld(self):
        mask = self._mask("weed")
        mask["box"] = {}
        output = self.runner.spray_map_node({"masks": [mask]})
        self.assertEqual(self._features(output), [])

    def test_label_mixing_weed_and_crop_prompt_words_is_withheld(self):
        # Real run, 17 Oct: prompt "weed . cotton plant ." produced the label "weed plant".
        state = {"masks": [self._mask("weed plant")], "text_prompt": "weed . cotton plant ."}
        output = self.runner.spray_map_node(state)
        self.assertEqual(self._features(output), [])
        self.assertEqual(output["spray_map"]["withheld_masks"][0]["label"], "weed plant")

    def test_mask_covering_most_of_the_photo_is_not_one_plant(self):
        # 18 Oct: with tiling, crop exclusion turned a whole-photo "weed" mask from
        # suppressed (above 85%) into a 61% spray of the field.
        output = self.runner.spray_map_node({"masks": [self._mask("weed", fill=0.6)]})
        self.assertEqual(self._features(output), [])
        self.assertIn("not one plant", output["spray_map"]["withheld_masks"][0]["reason"])

    def test_status_says_nothing_to_spray_when_no_zone_is_approved(self):
        # Issue #8: the status claimed a prescription when the map was empty.
        output = self.runner.spray_map_node({"masks": [self._mask("cotton")]})
        self.assertTrue(output["spray_map"]["status"].startswith("No weed zones approved"))

    def test_speck_fragments_are_dropped_and_zone_is_one_feature(self):
        # A mock run exported 1,394 features for 3 weeds: every 1-pixel island became a spray order.
        mask = np.zeros((480, 640), dtype=np.uint8)
        mask[100:200, 100:200] = 1
        for x in range(300, 600, 10):
            mask[50, x] = 1  # thirty isolated single pixels
        zone = {"label": "weed", "score": 0.9, "mask": mask}
        artifact = Artifact(
            id="spray",
            type=ArtifactType.SPRAY_MAP,
            title="Approved masks",
            payload={"approved_spray_zones": [zone]},
        )
        features = build_spray_geojson(
            {"spray_map": {"spray_allowed": True}, "artifacts": {"spray_map": artifact}}
        )["features"]
        self.assertEqual(len(features), 1)
        self.assertEqual(len(features[0]["geometry"]["coordinates"]), 1)

    def test_no_herbicide_in_export_without_a_prescription(self):
        # Issue #7: a hard-coded Pyrithiobac-sodium appeared when System 2 never ran.
        output = self.runner.spray_map_node({"masks": [self._mask("weed")]})
        geojson = build_spray_geojson(
            {"spray_map": output["spray_map"], "artifacts": output["artifacts"]}
        )
        self.assertEqual(len(geojson["features"]), 1)
        self.assertNotIn("active_ingredient", geojson["features"][0]["properties"])
        self.assertEqual(geojson["metadata"]["statutory_status"], "no_prescription")
        self.assertIn("Not GPS", geojson["metadata"]["coordinate_note"])

    def test_raw_unapproved_box_cannot_reach_export(self):
        approved_mask = np.zeros((12, 12), dtype=np.uint8)
        approved_mask[3:9, 2:7] = 1
        safe_zone = {"label": "grass", "score": 0.9, "mask": approved_mask}
        artifact = Artifact(
            id="spray",
            type=ArtifactType.SPRAY_MAP,
            title="Approved masks",
            payload={"approved_spray_zones": [safe_zone]},
        )
        features = build_spray_geojson(
            {
                "spray_map": {"spray_allowed": True, "safety_action": "ACCEPT"},
                "artifacts": {"spray_map": artifact},
                "boxes": [{"label": "weed", "x1": 0, "y1": 0, "x2": 500, "y2": 400}],
            }
        )["features"]
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["properties"]["target"], "grass")
        self.assertNotEqual(features[0]["properties"]["target"], "weed")
        polygon_points = features[0]["geometry"]["coordinates"][0][0]
        longitudes = [point[0] for point in polygon_points]
        self.assertLess(max(longitudes) - min(longitudes), 0.0001)


if __name__ == "__main__":
    unittest.main()
