"""Regression tests for the approved-mask spray/export contract."""

import unittest

import numpy as np

from app.components.pipeline import build_spray_geojson
from src.state import Artifact, ArtifactType
from src.workflow import VisionWorkflowRunner


class SprayExportSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = VisionWorkflowRunner(mock_mode=True)

    def _mask(self, label: str, fill: float = 0.05):
        pixels = np.zeros((480, 640), dtype=bool)
        pixels[: int(480 * fill), :640] = True
        return {"label": label, "mask_array": pixels, "predicted_iou": 0.95, "box": {}}

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
        output = self.runner.spray_map_node({"masks": [self._mask("weed", fill=0.90)]})
        self.assertEqual(output["spray_map"]["safety_action"], "SUPPRESS_SPRAY")
        self.assertFalse(output["spray_map"]["spray_allowed"])
        self.assertEqual(self._features(output), [])

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
        polygon_points = features[0]["geometry"]["coordinates"][0]
        longitudes = [point[0] for point in polygon_points]
        self.assertLess(max(longitudes) - min(longitudes), 0.0001)


if __name__ == "__main__":
    unittest.main()
