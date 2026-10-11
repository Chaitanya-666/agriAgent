"""
tests/test_benchmark_runner.py
Unit tests for the independent vision evaluation benchmark harness (src/evaluation/benchmark_runner.py).
"""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from src.evaluation.benchmark_runner import (
    BenchmarkRunner,
    compute_box_iou,
    rasterize_annotation_mask,
    rasterize_ground_truth,
)


class TestBenchmarkRunner(unittest.TestCase):
    """Test suite for BenchmarkRunner, rasterization, box IoU, and metric aggregations."""

    def setUp(self):
        self.manifest_path = Path("data/manifests/eval_manifest_v1.json")
        self.runner = BenchmarkRunner(
            manifest_path=self.manifest_path,
            mock_mode=True,
        )

    def test_compute_box_iou_identical(self):
        """Identical boxes must return an IoU of exactly 1.0."""
        box = (10.0, 10.0, 50.0, 50.0)
        self.assertAlmostEqual(compute_box_iou(box, box), 1.0, places=5)

    def test_compute_box_iou_disjoint(self):
        """Completely disjoint boxes must return an IoU of 0.0."""
        box_a = (0.0, 0.0, 10.0, 10.0)
        box_b = (20.0, 20.0, 30.0, 30.0)
        self.assertEqual(compute_box_iou(box_a, box_b), 0.0)

    def test_compute_box_iou_partial_overlap(self):
        """Known partial overlap calculates exact mathematical ratio."""
        # Box A: 10x10 = 100, Box B: 10x10 = 100, Inter: 5x10 = 50, Union: 150 -> IoU = 1/3
        box_a = (0.0, 0.0, 10.0, 10.0)
        box_b = (5.0, 0.0, 15.0, 10.0)
        expected_iou = 50.0 / 150.0
        self.assertAlmostEqual(compute_box_iou(box_a, box_b), expected_iou, places=5)

    def test_compute_box_iou_zero_area(self):
        """Degenerate zero-area boxes must return an IoU of 0.0 without division by zero."""
        box_a = (5.0, 5.0, 5.0, 5.0)
        box_b = (0.0, 0.0, 10.0, 10.0)
        self.assertEqual(compute_box_iou(box_a, box_b), 0.0)

    def test_rasterize_annotation_mask_polygon(self):
        """Rasterizing a polygon produces a boolean mask with expected shape and positive area."""
        poly = [10.0, 10.0, 30.0, 10.0, 30.0, 30.0, 10.0, 30.0]
        ann = {"segmentation": [poly], "category": "weed"}
        mask = rasterize_annotation_mask(ann, width=100, height=80)
        self.assertEqual(mask.shape, (80, 100))
        self.assertEqual(mask.dtype, bool)
        self.assertGreater(mask.sum(), 0)

    def test_rasterize_annotation_mask_box_fallback(self):
        """When segmentation is absent, rasterizer falls back to rectangular box."""
        ann = {"box": [10, 10, 30, 20], "category": "crop"}
        mask = rasterize_annotation_mask(ann, width=100, height=50)
        self.assertEqual(mask.shape, (50, 100))
        # Expected area = (30 - 10) * (20 - 10) = 20 * 10 = 200 (or slightly larger due to pixel border)
        self.assertGreaterEqual(mask.sum(), 200)

    def test_rasterize_ground_truth_category_filter(self):
        """Ground truth rasterization correctly filters by category."""
        annotations = [
            {"id": "1", "category": "crop", "box": [0, 0, 10, 10]},
            {"id": "2", "category": "weed", "box": [20, 20, 30, 30]},
        ]
        crop_mask = rasterize_ground_truth(annotations, 50, 50, category="crop")
        weed_mask = rasterize_ground_truth(annotations, 50, 50, category="weed")
        all_mask = rasterize_ground_truth(annotations, 50, 50, category=None)

        self.assertGreater(crop_mask.sum(), 0)
        self.assertGreater(weed_mask.sum(), 0)
        self.assertEqual(np.logical_and(crop_mask, weed_mask).sum(), 0)
        self.assertEqual(all_mask.sum(), crop_mask.sum() + weed_mask.sum())

    def test_load_manifest_success(self):
        """Loading manifest returns valid JSON structure with items."""
        data = self.runner.load_manifest()
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 20)
        self.assertIn("split_summary", data)

    def test_load_manifest_file_not_found(self):
        """Loading a non-existent manifest file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.runner.load_manifest("non_existent_file.json")

    def test_evaluate_single_image(self):
        """Evaluating a single image from the manifest returns populated ImageBenchmarkResult."""
        manifest = self.runner.load_manifest()
        first_item = manifest["items"][0]
        res = self.runner.evaluate_image(first_item)

        self.assertEqual(res.image_id, first_item["image_id"])
        self.assertEqual(res.crop_type, first_item["crop_type"])
        self.assertEqual(res.width, first_item["width"])
        self.assertEqual(res.height, first_item["height"])
        self.assertGreater(res.num_gt_boxes, 0)
        self.assertGreaterEqual(res.precision, 0.0)
        self.assertLessEqual(res.precision, 1.0)
        self.assertGreaterEqual(res.recall, 0.0)
        self.assertLessEqual(res.recall, 1.0)
        self.assertGreaterEqual(res.pred_chemical_savings, 0.0)
        self.assertLessEqual(res.pred_chemical_savings, 100.0)
        self.assertGreater(res.total_latency_ms, 0.0)

    def test_run_benchmark_max_samples(self):
        """Passing max_samples limits the evaluation batch to specified count."""
        out = self.runner.run_benchmark(max_samples=2)
        summary = out["summary"]
        self.assertEqual(summary["num_images_evaluated"], 2)
        self.assertEqual(len(out["per_image_results"]), 2)

    def test_run_benchmark_splits(self):
        """Benchmarking with split='val' and split='test' evaluates exactly 10 images each."""
        val_out = self.runner.run_benchmark(split="val")
        self.assertEqual(val_out["summary"]["num_images_evaluated"], 10)
        for r in val_out["per_image_results"]:
            self.assertEqual(r["split"], "val")

        test_out = self.runner.run_benchmark(split="test")
        self.assertEqual(test_out["summary"]["num_images_evaluated"], 10)
        for r in test_out["per_image_results"]:
            self.assertEqual(r["split"], "test")

    def test_run_benchmark_invalid_split(self):
        """Non-existent split with 0 items raises ValueError."""
        with self.assertRaises(ValueError):
            self.runner.run_benchmark(split="non_existent_split")

    def test_metric_aggregation_consistency(self):
        """Aggregate TP, FP, and FN in summary match sum of individual image results."""
        out = self.runner.run_benchmark(max_samples=4)
        summary = out["summary"]
        per_img = out["per_image_results"]

        expected_tp = sum(r["detection_tp"] for r in per_img)
        expected_fp = sum(r["detection_fp"] for r in per_img)
        expected_fn = sum(r["detection_fn"] for r in per_img)

        self.assertEqual(summary["detection"]["tp"], expected_tp)
        self.assertEqual(summary["detection"]["fp"], expected_fp)
        self.assertEqual(summary["detection"]["fn"], expected_fn)

    def test_per_crop_breakdown(self):
        """Per-crop breakdown contains stats for both cotton and sugarbeet."""
        out = self.runner.run_benchmark(split="all")
        crops = out["summary"]["per_crop"]
        self.assertIn("cotton", crops)
        self.assertIn("sugarbeet", crops)
        self.assertEqual(crops["cotton"]["num_images"], 10)
        self.assertEqual(crops["sugarbeet"]["num_images"], 10)

    def test_format_markdown_report(self):
        """Markdown formatter generates publication-ready summary string with table."""
        out = self.runner.run_benchmark(max_samples=2)
        report = self.runner.format_markdown_report(out)
        self.assertIsInstance(report, str)
        self.assertIn("# AgriAgent Vision Benchmark Evaluation Report", report)
        self.assertIn("Precision", report)
        self.assertIn("Mean Weed Mask IoU", report)
        self.assertIn("Predicted Chemical Savings", report)

    def test_resolve_image_path_error(self):
        """Invalid item with unresolvable image raises FileNotFoundError."""
        bad_item = {"image_id": "totally_fake_image_12345.png", "image_path": "fake/path.png"}
        with self.assertRaises(FileNotFoundError):
            self.runner.resolve_image_path(bad_item)


if __name__ == "__main__":
    unittest.main()
