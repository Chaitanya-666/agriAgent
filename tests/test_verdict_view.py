"""F28: the optional view colours every plant by the decision taken."""

import unittest

import numpy as np
from PIL import Image

from app.app import run_pipeline_on_image
from app.components.pipeline import create_sample_field_image
from app.components.ui import plant_verdict_image
from src.vision.visualization import VERDICT_COLORS, verdict_view


class VerdictViewTests(unittest.TestCase):
    def test_priority_sprayed_over_crop_over_unsure(self):
        image = Image.new("RGB", (4, 1), (0, 0, 0))
        sprayed = np.array([[1, 0, 0, 0]], dtype=bool)
        crop = np.array([[1, 1, 0, 0]], dtype=bool)
        vegetation = np.array([[1, 1, 1, 0]], dtype=bool)
        view, counts = verdict_view(image, sprayed, crop, vegetation, alpha=1.0)
        self.assertEqual(counts, {"sprayed": 1, "crop": 1, "unsure": 1})
        pixels = np.asarray(view)[0]
        self.assertEqual(tuple(pixels[0]), VERDICT_COLORS["sprayed"])
        self.assertEqual(tuple(pixels[1]), VERDICT_COLORS["crop"])
        self.assertEqual(tuple(pixels[2]), VERDICT_COLORS["unsure"])
        self.assertEqual(tuple(pixels[3]), (0, 0, 0))

    def test_mismatched_mask_shapes_do_not_crash(self):
        image = Image.new("RGB", (5, 4))
        view, _ = verdict_view(
            image, np.ones((2, 2), bool), np.ones((6, 6), bool), np.ones((4, 5), bool)
        )
        self.assertEqual(view.size, (5, 4))

    def test_mock_run_gives_a_view(self):
        image = create_sample_field_image()
        _, state, _ = run_pipeline_on_image(image, mock_mode=True, crop="cotton")
        view, counts = plant_verdict_image(image, state)
        self.assertEqual(view.size, image.size)
        self.assertGreater(sum(counts.values()), 0)


if __name__ == "__main__":
    unittest.main()
