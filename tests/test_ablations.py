"""
tests/test_ablations.py
Comprehensive unit test suite for AgriAgent Ablation Runner (Milestone 5).

Verifies:
- AblationRunner initialization and manifest loading.
- Parameterized morphological error centroid calculation and edge clamping.
- Ablation A (baseline Grounding DINO + SAM 2 without refinement).
- Ablation B (Grounding DINO + SAM 2 with morphological refinement).
- Ablation C (parameter sweeps over refinement thresholds and morphological operators).
- Ablation D (Deterministic vs Laya router latency and decision benchmark).
- Ablation E (Cloudflare Clef Flash vs local fail-safe network fallback).
- JSON summary serialization and schema compliance.
- Defensive error handling (missing manifest, empty split).
"""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from src.agents.router_contract import RouterAction
from src.evaluation.ablation_runner import (
    AblationMetrics,
    AblationRunner,
    parameterized_error_centroid,
)
from src.vision.sam2_wrapper import SAM2Segmenter


class TestParameterizedRefinementCentroid(unittest.TestCase):
    """Test suite for parameterized morphological error centroid calculations."""

    def setUp(self) -> None:
        self.height, self.width = 100, 100
        self.box = (20.0, 20.0, 80.0, 80.0)

    def test_empty_mask_inside_box_returns_center_positive(self) -> None:
        """When mask inside bounding box is empty, must return center as positive prompt."""
        empty_mask = np.zeros((self.height, self.width), dtype=bool)
        cx, cy, is_positive = parameterized_error_centroid(empty_mask, self.box)
        self.assertTrue(is_positive)
        self.assertEqual(cx, 50)
        self.assertEqual(cy, 50)

    def test_over_segmentation_leak_returns_negative_prompt(self) -> None:
        """When mask heavily leaks outside bounding box, must prompt negative point outside box."""
        leaking_mask = np.zeros((self.height, self.width), dtype=bool)
        # Inside box
        leaking_mask[30:50, 30:50] = True
        # Large leak outside box
        leaking_mask[5:15, 5:15] = True
        leaking_mask[85:95, 85:95] = True

        cx, cy, is_positive = parameterized_error_centroid(leaking_mask, self.box)
        self.assertFalse(is_positive)
        # Verify point is outside the bounding box
        is_outside = cx < 20 or cx >= 80 or cy < 20 or cy >= 80
        self.assertTrue(is_outside)

    def test_canopy_indentation_returns_positive_prompt(self) -> None:
        """When canopy has internal gap, must prompt positive corrective point."""
        donut_mask = np.zeros((self.height, self.width), dtype=bool)
        donut_mask[25:75, 25:75] = True
        # Hollow center hole inside box
        donut_mask[45:55, 45:55] = False

        cx, cy, is_positive = parameterized_error_centroid(donut_mask, self.box, radius=3)
        self.assertTrue(is_positive)
        self.assertTrue(20 <= cx < 80)
        self.assertTrue(20 <= cy < 80)

    def test_excess_green_weighting_with_rgb_image(self) -> None:
        """Excess Green weighting prioritizes pixels with high vegetation index (2G - R - B)."""
        mask = np.zeros((self.height, self.width), dtype=bool)
        mask[30:70, 30:70] = True

        # Synthesize RGB image with bright green leaf patch at top edge
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[28:30, 48:52] = [20, 220, 20]  # Intense green vegetation

        cx, cy, is_positive = parameterized_error_centroid(
            mask,
            self.box,
            radius=2,
            exg_weighting=True,
            image=img,
        )
        self.assertTrue(is_positive)
        self.assertTrue(0 <= cx < self.width)
        self.assertTrue(0 <= cy < self.height)


class TestAblationRunnerCore(unittest.TestCase):
    """Test suite for AblationRunner ablations A through E."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_path = "data/manifests/eval_manifest_v1.json"
        cls.runner = AblationRunner(
            manifest_path=cls.manifest_path,
            mock_mode=True,
        )

    def test_runner_initialization(self) -> None:
        """Verify proper initialization and component attachment."""
        self.assertTrue(self.runner.mock_mode)
        self.assertIsNotNone(self.runner.detector)
        self.assertIsNotNone(self.runner.segmenter)
        self.assertTrue(self.runner.manifest_path.exists())

    def test_run_ablation_a_baseline(self) -> None:
        """Verify Ablation A executes baseline evaluation without refinement."""
        metrics_a = self.runner.run_ablation_a(split="val", max_samples=2)
        self.assertIsInstance(metrics_a, AblationMetrics)
        self.assertEqual(metrics_a.ablation_name, "Ablation A")
        self.assertEqual(metrics_a.num_images, 2)
        self.assertGreater(metrics_a.mean_plant_iou, 0.0)
        self.assertGreater(metrics_a.mean_pred_chemical_savings_pct, 0.0)
        self.assertEqual(metrics_a.mean_refinement_latency_ms, 0.0)
        self.assertFalse(metrics_a.extra_details["refinement_enabled"])
        self.assertEqual(metrics_a.extra_details["masks_refined"], 0)

    def test_run_ablation_b_with_refinement(self) -> None:
        """Verify Ablation B executes with active morphological refinement."""
        metrics_b, deltas = self.runner.run_ablation_b(
            split="val",
            max_samples=2,
            iou_threshold=0.90,
        )
        self.assertIsInstance(metrics_b, AblationMetrics)
        self.assertEqual(metrics_b.ablation_name, "Ablation B")
        self.assertEqual(metrics_b.num_images, 2)
        self.assertTrue(metrics_b.extra_details["refinement_enabled"])
        self.assertGreater(metrics_b.extra_details["masks_refined"], 0)
        self.assertGreater(metrics_b.mean_refinement_latency_ms, 0.0)

        # Delta checks
        self.assertIn("delta_plant_iou", deltas)
        self.assertIn("delta_weed_iou", deltas)
        self.assertIn("delta_chemical_savings", deltas)
        self.assertIn("latency_overhead_ms", deltas)

    def test_run_ablation_c_parameter_sweeps(self) -> None:
        """Verify Ablation C parameter sweeps over compact grid."""
        compact_grid = {
            "iou_threshold": [0.80, 0.90],
            "kernel_radius": [1, 2],
            "erosion_iterations": [1],
            "exg_weighting": [True, False],
        }
        res_c = self.runner.run_ablation_c(
            split="val",
            max_samples=2,
            sweep_grid=compact_grid,
        )
        self.assertEqual(res_c["num_combinations_evaluated"], 8)
        self.assertIn("best_config", res_c)
        self.assertIn("all_results", res_c)
        self.assertEqual(len(res_c["all_results"]), 8)

        best = res_c["best_config"]
        self.assertIn("mean_plant_iou", best)
        self.assertIn("config", best)
        self.assertIn("refinement_trigger_rate", best)

    def test_run_ablation_d_router_comparison(self) -> None:
        """Verify Ablation D router comparison between Deterministic and Laya routers."""
        res_d = self.runner.run_ablation_d(num_trials=20)
        self.assertIn("deterministic_router", res_d)
        self.assertIn("laya_router", res_d)
        self.assertIn("speedup_factor_deterministic_vs_laya", res_d)

        det = res_d["deterministic_router"]
        laya = res_d["laya_router"]

        self.assertEqual(det["backend"], "deterministic")
        self.assertEqual(laya["backend"], "laya")
        self.assertEqual(det["decision_accuracy"], 1.0)
        self.assertEqual(laya["decision_accuracy"], 1.0)

        # Verify action distribution coverage
        for act in [
            RouterAction.ACCEPT,
            RouterAction.REFINE,
            RouterAction.ESCALATE_SYSTEM2,
            RouterAction.SUPPRESS_SPRAY,
        ]:
            self.assertGreater(det["action_distribution"][act.value], 0)
            self.assertGreater(laya["action_distribution"][act.value], 0)

        # Latency metrics exist and are positive
        self.assertGreater(det["mean_latency_ms"], 0.0)
        self.assertGreater(laya["mean_latency_ms"], 0.0)

    def test_run_ablation_e_clef_flash_and_resilience(self) -> None:
        """Verify Ablation E multimodal routing and fail-safe network drop fallback."""
        res_e = self.runner.run_ablation_e(num_trials=10, simulate_network_failure=True)
        self.assertIn("clef_flash_normal", res_e)
        self.assertIn("fail_safe_network_resilience", res_e)

        norm = res_e["clef_flash_normal"]
        self.assertTrue(norm["multimodal_supported"])
        self.assertEqual(norm["decision_accuracy"], 1.0)

        resilience = res_e["fail_safe_network_resilience"]
        self.assertEqual(resilience["fallback_success_rate"], 1.0)
        self.assertEqual(resilience["unhandled_crashes"], 0)
        self.assertGreater(resilience["simulated_dropouts"], 0)

    def test_run_all_ablations_writes_valid_json(self) -> None:
        """Verify run_all_ablations produces structured, schema-compliant JSON artifact."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "test_ablations_summary.json"
            summary = self.runner.run_all_ablations(
                output_path=out_file,
                split="val",
                max_samples=2,
            )

            self.assertTrue(out_file.exists())
            with open(out_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            self.assertIn("metadata", loaded)
            self.assertIn("ablation_a", loaded)
            self.assertIn("ablation_b", loaded)
            self.assertIn("comparison_ab_deltas", loaded)
            self.assertIn("ablation_c", loaded)
            self.assertIn("ablation_d", loaded)
            self.assertIn("ablation_e", loaded)

            self.assertEqual(loaded["ablation_a"]["num_images"], 2)
            self.assertEqual(loaded["ablation_b"]["num_images"], 2)
            self.assertEqual(summary["metadata"]["split"], "val")

    def test_missing_manifest_raises_error(self) -> None:
        """Verify proper FileNotFoundError when manifest file does not exist."""
        bad_runner = AblationRunner(manifest_path="non_existent_manifest.json")
        with self.assertRaises(FileNotFoundError):
            bad_runner.run_ablation_a()

    def test_empty_split_raises_error(self) -> None:
        """Verify proper ValueError when non-existent split is requested."""
        with self.assertRaises(ValueError):
            self.runner.run_ablation_a(split="unknown_split_name")


if __name__ == "__main__":
    unittest.main()
