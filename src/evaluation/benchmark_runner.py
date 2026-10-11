"""
src/evaluation/benchmark_runner.py
Independent vision evaluation harness for Grounding DINO and SAM 2.

Evaluates object detection and instance segmentation predictions against
verified ground-truth annotations using compute_iou and compute_dice.
Supports both live deep-learning inference (GPU) and deterministic mock fallbacks (CPU).
"""

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw

import sys
from pathlib import Path

# Ensure repository root is on sys.path for direct CLI invocations
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.evaluation.iou_dice import (
    compute_dice,
    compute_herbicide_savings,
    compute_iou,
    evaluate_batch,
)
from src.state import Box
from src.vision.grounding_dino import GroundingDINOEngine
from src.vision.sam2_wrapper import SAM2Segmenter

logger = logging.getLogger("agriagent.evaluation.benchmark")


def compute_box_iou(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> float:
    """
    Compute Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2].
    """
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b

    inter_x1 = max(xa1, xb1)
    inter_y1 = max(ya1, yb1)
    inter_x2 = min(xa2, xb2)
    inter_y2 = min(ya2, yb2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, xa2 - xa1) * max(0.0, ya2 - ya1)
    area_b = max(0.0, xb2 - xb1) * max(0.0, yb2 - yb1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0
    return float(inter_area / union_area)


def rasterize_annotation_mask(
    annotation: Dict[str, Any],
    width: int,
    height: int,
) -> np.ndarray:
    """
    Rasterize an individual ground-truth annotation's polygon or bounding box
    into a 2D boolean mask of shape [height, width].
    """
    mask_img = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(mask_img)

    seg = annotation.get("segmentation")
    if seg and len(seg) > 0:
        for poly in seg:
            if len(poly) >= 6:  # Valid polygon (at least 3 (x, y) coordinate pairs)
                draw.polygon(poly, outline=1, fill=1)
            elif len(poly) == 4:  # Bounding box fallback
                draw.rectangle(poly, outline=1, fill=1)
    elif "box" in annotation:
        box = annotation["box"]
        draw.rectangle([box[0], box[1], box[2], box[3]], outline=1, fill=1)

    return np.array(mask_img, dtype=bool)


def rasterize_ground_truth(
    annotations: List[Dict[str, Any]],
    width: int,
    height: int,
    category: Optional[str] = None,
) -> np.ndarray:
    """
    Rasterize and combine multiple annotations into a single union 2D boolean mask.
    Optionally filters by semantic category ('crop' or 'weed').
    """
    combined_mask = np.zeros((height, width), dtype=bool)
    for ann in annotations:
        if category is not None and ann.get("category") != category:
            continue
        mask = rasterize_annotation_mask(ann, width, height)
        combined_mask |= mask
    return combined_mask


@dataclass
class ImageBenchmarkResult:
    """Container for per-image evaluation metrics."""
    image_id: str
    crop_type: str
    split: str
    width: int
    height: int
    num_gt_boxes: int
    num_pred_boxes: int
    detection_tp: int
    detection_fp: int
    detection_fn: int
    precision: float
    recall: float
    f1: float
    mean_box_iou: float
    weed_mask_iou: float
    weed_mask_dice: float
    plant_mask_iou: float
    plant_mask_dice: float
    pred_chemical_savings: float
    gt_chemical_savings: float
    infestation_percentage: float
    detection_latency_ms: float
    segmentation_latency_ms: float
    total_latency_ms: float


class BenchmarkRunner:
    """
    Automated evaluation harness for AgriAgent perception pipeline.
    Loads versioned evaluation manifests, executes detection & segmentation,
    and computes precision, recall, F1, mean IoU, mean Dice, latency, and chemical savings.
    """

    def __init__(
        self,
        manifest_path: Union[str, Path] = "data/manifests/eval_manifest_v1.json",
        iou_threshold: float = 0.50,
        detector: Optional[GroundingDINOEngine] = None,
        segmenter: Optional[SAM2Segmenter] = None,
        mock_mode: Optional[bool] = None,
        default_prompt: str = "cotton weed . sugar beet weed . broadleaf weed . crop .",
    ):
        self.manifest_path = Path(manifest_path)
        self.iou_threshold = iou_threshold
        self.default_prompt = default_prompt

        # Initialize detector with mock fallback
        if detector is not None:
            self.detector = detector
        else:
            self.detector = GroundingDINOEngine(mock_mode=mock_mode if mock_mode is not None else False)

        # Initialize segmenter with mock fallback
        if segmenter is not None:
            self.segmenter = segmenter
        else:
            self.segmenter = SAM2Segmenter(mock_mode=mock_mode if mock_mode is not None else False)

    def load_manifest(self, path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Load manifest JSON file."""
        target_path = Path(path) if path is not None else self.manifest_path
        if not target_path.exists():
            raise FileNotFoundError(f"Evaluation manifest not found at: {target_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    def resolve_image_path(self, item: Dict[str, Any]) -> Path:
        """Resolve absolute path to image file with defensive fallback search."""
        candidate_paths = [
            Path(item.get("image_path", "")),
            Path(item.get("relative_path", "")),
            Path("tests/fixtures/sample") / item.get("image_id", ""),
            Path("tests/fixtures/cotton") / item.get("image_id", ""),
            Path("tests/fixtures/sugarbeet") / item.get("image_id", ""),
        ]

        for p in candidate_paths:
            if p.exists() and p.is_file():
                return p.resolve()

        raise FileNotFoundError(f"Image not found for item {item.get('image_id')}. Checked: {candidate_paths}")

    def evaluate_image(
        self,
        item: Dict[str, Any],
        text_prompt: Optional[str] = None,
    ) -> ImageBenchmarkResult:
        """
        Execute detection and segmentation on a single image and compute all evaluation metrics.
        """
        img_path = self.resolve_image_path(item)
        pil_img = Image.open(img_path).convert("RGB")
        width, height = pil_img.size

        prompt = text_prompt or self.default_prompt
        crop_type = item.get("crop_type", "unknown")
        split = item.get("split", "eval")
        gt_annotations = item.get("annotations", [])

        # 1. Detection Stage
        t0 = time.perf_counter()
        raw_detections = self.detector.detect(pil_img, text_prompt=prompt)
        t1 = time.perf_counter()
        detection_latency_ms = (t1 - t0) * 1000.0

        # Convert detections to standardized Box format
        pred_boxes: List[Box] = [
            d.to_dict() if hasattr(d, "to_dict") else d
            for d in raw_detections
        ]

        # 2. Segmentation Stage
        t2 = time.perf_counter()
        raw_masks = self.segmenter.segment_boxes(pil_img, pred_boxes)
        t3 = time.perf_counter()
        segmentation_latency_ms = (t3 - t2) * 1000.0
        total_latency_ms = (t3 - t0) * 1000.0

        # Extract predicted 2D boolean mask arrays
        pred_mask_arrays: List[np.ndarray] = []
        for m in raw_masks:
            arr = m.mask_array if hasattr(m, "mask_array") else m.get("mask_array")
            if isinstance(arr, np.ndarray) and arr.shape == (height, width):
                pred_mask_arrays.append(arr.astype(bool))

        # 3. Detection Matching (Box IoU)
        gt_boxes = [ann["box"] for ann in gt_annotations if "box" in ann]
        matched_gt = set()
        matched_pred = set()
        matched_ious: List[float] = []

        for p_idx, p_box in enumerate(pred_boxes):
            p_coords = (p_box["x1"], p_box["y1"], p_box["x2"], p_box["y2"])
            best_iou = 0.0
            best_gt_idx = -1
            for g_idx, g_coords in enumerate(gt_boxes):
                if g_idx in matched_gt:
                    continue
                iou = compute_box_iou(p_coords, tuple(g_coords))
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = g_idx

            if best_iou >= self.iou_threshold and best_gt_idx >= 0:
                matched_gt.add(best_gt_idx)
                matched_pred.add(p_idx)
                matched_ious.append(best_iou)

        tp = len(matched_gt)
        fp = len(pred_boxes) - len(matched_pred)
        fn = len(gt_boxes) - len(matched_gt)

        precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        mean_box_iou = float(np.mean(matched_ious)) if matched_ious else 0.0

        # 4. Segmentation Evaluation (IoU & Dice against Ground Truth)
        gt_weed_mask = rasterize_ground_truth(gt_annotations, width, height, category="weed")
        gt_all_mask = rasterize_ground_truth(gt_annotations, width, height)

        pred_weed_union = np.zeros((height, width), dtype=bool)
        pred_all_union = np.zeros((height, width), dtype=bool)

        for p_box, m_arr in zip(pred_boxes, pred_mask_arrays):
            pred_all_union |= m_arr
            label_lower = str(p_box.get("label", "")).lower()
            if "weed" in label_lower or "vegetation" in label_lower or "unwanted" in label_lower:
                pred_weed_union |= m_arr

        # If no explicit weed label matched, treat all predictions as spray targets
        if pred_weed_union.sum() == 0 and pred_all_union.sum() > 0:
            pred_weed_union = pred_all_union.copy()

        weed_iou = compute_iou(pred_weed_union, gt_weed_mask)
        weed_dice = compute_dice(pred_weed_union, gt_weed_mask)
        plant_iou = compute_iou(pred_all_union, gt_all_mask)
        plant_dice = compute_dice(pred_all_union, gt_all_mask)

        # 5. Agronomic Metrics (Chemical Savings & Infestation)
        pred_savings = compute_herbicide_savings(pred_weed_union, (height, width))
        gt_savings = compute_herbicide_savings(gt_weed_mask, (height, width))
        infestation_pct = float((gt_weed_mask.sum() / (width * height)) * 100.0)

        return ImageBenchmarkResult(
            image_id=item.get("image_id", img_path.name),
            crop_type=crop_type,
            split=split,
            width=width,
            height=height,
            num_gt_boxes=len(gt_boxes),
            num_pred_boxes=len(pred_boxes),
            detection_tp=tp,
            detection_fp=fp,
            detection_fn=fn,
            precision=precision,
            recall=recall,
            f1=f1,
            mean_box_iou=mean_box_iou,
            weed_mask_iou=weed_iou,
            weed_mask_dice=weed_dice,
            plant_mask_iou=plant_iou,
            plant_mask_dice=plant_dice,
            pred_chemical_savings=pred_savings,
            gt_chemical_savings=gt_savings,
            infestation_percentage=infestation_pct,
            detection_latency_ms=detection_latency_ms,
            segmentation_latency_ms=segmentation_latency_ms,
            total_latency_ms=total_latency_ms,
        )

    def run_benchmark(
        self,
        split: Optional[str] = None,
        max_samples: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run the evaluation benchmark across manifest items and return aggregate statistics.
        
        Args:
            split: Filter items by split ('val', 'test', or None for all items).
            max_samples: Maximum number of images to evaluate.
        """
        manifest = self.load_manifest()
        items: List[Dict[str, Any]] = manifest.get("items") or manifest.get("images") or []

        if split and split.lower() != "all":
            items = [item for item in items if item.get("split", "").lower() == split.lower()]

        if max_samples is not None and max_samples > 0:
            items = items[:max_samples]

        if not items:
            raise ValueError(f"No items found to evaluate with split={split}")

        per_image_results: List[ImageBenchmarkResult] = []
        for item in items:
            res = self.evaluate_image(item)
            per_image_results.append(res)

        # Aggregate metrics
        total_tp = sum(r.detection_tp for r in per_image_results)
        total_fp = sum(r.detection_fp for r in per_image_results)
        total_fn = sum(r.detection_fn for r in per_image_results)

        agg_precision = float(total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
        agg_recall = float(total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else 0.0
        agg_f1 = float(2 * agg_precision * agg_recall / (agg_precision + agg_recall)) if (agg_precision + agg_recall) > 0 else 0.0

        weed_ious = [r.weed_mask_iou for r in per_image_results]
        weed_dices = [r.weed_mask_dice for r in per_image_results]
        plant_ious = [r.plant_mask_iou for r in per_image_results]
        plant_dices = [r.plant_mask_dice for r in per_image_results]
        pred_savings = [r.pred_chemical_savings for r in per_image_results]
        gt_savings = [r.gt_chemical_savings for r in per_image_results]
        latencies = [r.total_latency_ms for r in per_image_results]

        # Per-crop breakdown
        crops = sorted(list(set(r.crop_type for r in per_image_results)))
        per_crop_summary = {}
        for c in crops:
            c_res = [r for r in per_image_results if r.crop_type == c]
            c_tp = sum(r.detection_tp for r in c_res)
            c_fp = sum(r.detection_fp for r in c_res)
            c_fn = sum(r.detection_fn for r in c_res)
            c_prec = float(c_tp / (c_tp + c_fp)) if (c_tp + c_fp) > 0 else 0.0
            c_rec = float(c_tp / (c_tp + c_fn)) if (c_tp + c_fn) > 0 else 0.0
            c_f1 = float(2 * c_prec * c_rec / (c_prec + c_rec)) if (c_prec + c_rec) > 0 else 0.0
            per_crop_summary[c] = {
                "num_images": len(c_res),
                "precision": c_prec,
                "recall": c_rec,
                "f1": c_f1,
                "mean_weed_iou": float(np.mean([r.weed_mask_iou for r in c_res])),
                "mean_weed_dice": float(np.mean([r.weed_mask_dice for r in c_res])),
                "mean_chemical_savings": float(np.mean([r.pred_chemical_savings for r in c_res])),
            }

        summary = {
            "num_images_evaluated": len(per_image_results),
            "split": split or "all",
            "manifest_version": manifest.get("manifest_version", manifest.get("version", "1.0.0")),
            "detection": {
                "precision": agg_precision,
                "recall": agg_recall,
                "f1": agg_f1,
                "tp": total_tp,
                "fp": total_fp,
                "fn": total_fn,
                "mean_box_iou": float(np.mean([r.mean_box_iou for r in per_image_results if r.mean_box_iou > 0] or [0.0])),
            },
            "segmentation": {
                "mean_weed_iou": float(np.mean(weed_ious)),
                "std_weed_iou": float(np.std(weed_ious)),
                "mean_weed_dice": float(np.mean(weed_dices)),
                "std_weed_dice": float(np.std(weed_dices)),
                "mean_plant_iou": float(np.mean(plant_ious)),
                "mean_plant_dice": float(np.mean(plant_dices)),
            },
            "agronomy": {
                "mean_pred_chemical_savings_pct": float(np.mean(pred_savings)),
                "mean_gt_chemical_savings_pct": float(np.mean(gt_savings)),
                "mean_infestation_pct": float(np.mean([r.infestation_percentage for r in per_image_results])),
            },
            "latency": {
                "mean_detection_ms": float(np.mean([r.detection_latency_ms for r in per_image_results])),
                "mean_segmentation_ms": float(np.mean([r.segmentation_latency_ms for r in per_image_results])),
                "mean_total_ms": float(np.mean(latencies)),
            },
            "per_crop": per_crop_summary,
        }

        return {
            "summary": summary,
            "per_image_results": [asdict(r) for r in per_image_results],
        }

    def format_markdown_report(self, benchmark_output: Dict[str, Any]) -> str:
        """Format benchmark results into a clean, publication-grade markdown summary."""
        s = benchmark_output["summary"]
        det = s["detection"]
        seg = s["segmentation"]
        agro = s["agronomy"]
        lat = s["latency"]

        lines = [
            "# AgriAgent Vision Benchmark Evaluation Report",
            f"**Split:** `{s['split']}` | **Samples Evaluated:** {s['num_images_evaluated']} | **Manifest Version:** `{s['manifest_version']}`",
            "",
            "## 1. Summary Metrics",
            "| Metric Category | Metric Name | Value |",
            "|---|---|---|",
            f"| **Detection** | Precision | {det['precision']:.4f} |",
            f"| **Detection** | Recall | {det['recall']:.4f} |",
            f"| **Detection** | F1-Score | {det['f1']:.4f} |",
            f"| **Detection** | Matches (TP / FP / FN) | {det['tp']} / {det['fp']} / {det['fn']} |",
            f"| **Segmentation** | Mean Weed Mask IoU | {seg['mean_weed_iou']:.4f} ± {seg['std_weed_iou']:.4f} |",
            f"| **Segmentation** | Mean Weed Mask Dice | {seg['mean_weed_dice']:.4f} ± {seg['std_weed_dice']:.4f} |",
            f"| **Segmentation** | Mean Plant Mask IoU | {seg['mean_plant_iou']:.4f} |",
            f"| **Agronomy** | Predicted Chemical Savings | {agro['mean_pred_chemical_savings_pct']:.2f}% |",
            f"| **Agronomy** | Ground-Truth Savings | {agro['mean_gt_chemical_savings_pct']:.2f}% |",
            f"| **Agronomy** | Field Infestation Rate | {agro['mean_infestation_pct']:.2f}% |",
            f"| **Latency** | End-to-End Latency | {lat['mean_total_ms']:.2f} ms |",
            f"| **Latency** | Detection Latency | {lat['mean_detection_ms']:.2f} ms |",
            f"| **Latency** | Segmentation Latency | {lat['mean_segmentation_ms']:.2f} ms |",
            "",
            "## 2. Per-Crop Breakdown",
            "| Crop | Images | Precision | Recall | F1 | Weed IoU | Weed Dice | Chemical Savings |",
            "|---|---|---|---|---|---|---|---|",
        ]

        for crop, cdata in s.get("per_crop", {}).items():
            lines.append(
                f"| `{crop}` | {cdata['num_images']} | {cdata['precision']:.4f} | {cdata['recall']:.4f} | "
                f"{cdata['f1']:.4f} | {cdata['mean_weed_iou']:.4f} | {cdata['mean_weed_dice']:.4f} | "
                f"{cdata['mean_chemical_savings']:.2f}% |"
            )

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="AgriAgent Vision Benchmark Harness")
    parser.add_argument("--manifest", type=str, default="data/manifests/eval_manifest_v1.json", help="Path to evaluation manifest JSON")
    parser.add_argument("--split", type=str, default="all", choices=["all", "val", "test"], help="Evaluation split to benchmark")
    parser.add_argument("--max-samples", type=int, default=None, help="Maximum number of images to evaluate")
    parser.add_argument("--mock", action="store_true", help="Force mock mode execution")
    parser.add_argument("--output", type=str, default=None, help="Path to save JSON benchmark output")
    parser.add_argument("--markdown-output", type=str, default=None, help="Path to save Markdown report")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    runner = BenchmarkRunner(
        manifest_path=args.manifest,
        mock_mode=True if args.mock else None,
    )

    results = runner.run_benchmark(split=args.split, max_samples=args.max_samples)
    md_report = runner.format_markdown_report(results)
    print("\n" + md_report + "\n")

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Saved JSON results to {args.output}")

    if args.markdown_output:
        md_p = Path(args.markdown_output)
        md_p.parent.mkdir(parents=True, exist_ok=True)
        with open(md_p, "w", encoding="utf-8") as f:
            f.write(md_report)
        print(f"Saved Markdown report to {args.markdown_output}")


if __name__ == "__main__":
    main()
