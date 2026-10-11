"""
src/evaluation/ablation_runner.py
Automated evaluation engine for controlled agricultural vision and routing ablations.

Executes controlled scientific experiments over versioned dataset manifests
(e.g., data/manifests/eval_manifest_v1.json):
- Ablation A: Grounding DINO + SAM 2 baseline without morphological refinement.
- Ablation B: Grounding DINO + SAM 2 with morphological refinement (refinement.py).
- Ablation C: Parameter sweeps over refinement thresholds and morphological operators
             (kernel_size / radius, erosion_iterations, Excess Green weighting).
- Ablation D: Deterministic router vs an explicitly mocked local triage contract
             (decision accuracy, latency distribution, action distribution).
- Ablation E: explicitly mocked Clef safety contract only.

Outputs structured, machine-readable summary metrics to
data/evaluation_results/ablations_summary.json.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

# Ensure project root is on sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.agents.clef_flash_router import ClefFlashRouter
from src.agents.deterministic_router import DeterministicRouter
from src.agents.router_contract import (
    BaseRouter,
    RouterAction,
    RouterBackend,
    RouterDecision,
)
from src.evaluation.benchmark_runner import (
    BenchmarkRunner,
    ImageBenchmarkResult,
    compute_box_iou,
    rasterize_ground_truth,
)
from src.evaluation.iou_dice import (
    compute_dice,
    compute_herbicide_savings,
    compute_iou,
)
from src.state import Box
from src.vision.grounding_dino import GroundingDINOEngine
from src.vision.refinement import (
    binary_closing,
    binary_dilation,
    binary_erosion,
    binary_opening,
    compute_error_centroid,
    normalize_box_coordinates,
    should_refine,
)
from src.vision.sam2_wrapper import SAM2Segmenter, SegmentResult

logger = logging.getLogger("agriagent.evaluation.ablation")


def _sanitize_for_json(obj: Any) -> Any:
    """
    Recursively converts NumPy scalars and arrays into standard JSON serializable types.
    """
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def parameterized_error_centroid(
    mask: np.ndarray,
    box: Tuple[float, float, float, float],
    radius: int = 2,
    erosion_iterations: int = 1,
    exg_weighting: bool = True,
    image: Optional[Union[np.ndarray, Image.Image]] = None,
) -> Tuple[int, int, bool]:
    """
    Parameterized morphological contour and boundary gradient refinement.

    Permits controlled sweeps across structuring element radius, erosion passes,
    and vegetation index (Excess Green: 2G - R - B) weighting.

    Args:
        mask: 2D boolean segmentation mask array of shape [H, W].
        box: (x1, y1, x2, y2) bounding box coordinates.
        radius: Morphological structuring element radius for dilation/closing.
        erosion_iterations: Number of erosion passes for boundary analysis.
        exg_weighting: If True and image provided, weight contour points by Excess Green.
        image: Optional RGB field image for spectral vegetation weighting.

    Returns:
        (cx, cy, is_positive): Selected corrective prompt point and polarity.
    """
    h, w = mask.shape
    xmin, ymin, xmax, ymax = normalize_box_coordinates(box, (h, w))

    box_mask = np.zeros((h, w), dtype=bool)
    box_mask[ymin:ymax, xmin:xmax] = True

    mask_in_box = mask & box_mask

    # Empty mask inside box: prompt center as positive
    if mask_in_box.sum() == 0:
        cx = int((xmin + xmax) // 2) if xmax > xmin else min(xmin, w - 1)
        cy = int((ymin + ymax) // 2) if ymax > ymin else min(ymin, h - 1)
        return (cx, cy, True)

    # Over-segmentation leakage outside bounding box
    leak_outside = mask & ~box_mask

    # Spurious background noise using morphological opening with configured radius
    opened = binary_opening(mask, radius=max(1, radius - 1))
    spurious_noise = (mask & ~opened) & box_mask

    # Canopy holes and indentations using morphological closing
    closed = binary_closing(mask, radius=max(2, radius + 1))
    canopy_holes = (closed & ~mask) & box_mask

    # Boundary contour halo using morphological gradient (dilation)
    dilated = binary_dilation(mask, radius=max(1, radius))
    for _ in range(max(0, erosion_iterations - 1)):
        dilated = binary_dilation(dilated, radius=1)
    contour_halo = (dilated & ~mask) & box_mask

    # Compute Excess Green weighting if enabled
    foliage_weights: Optional[np.ndarray] = None
    if exg_weighting and image is not None:
        try:
            if isinstance(image, Image.Image):
                np_img = np.array(image.convert("RGB"))
            elif isinstance(image, np.ndarray):
                np_img = image if image.ndim == 3 else np.stack([image] * 3, axis=-1)
            else:
                np_img = None

            if np_img is not None and np_img.shape[:2] == (h, w):
                r = np_img[..., 0].astype(float)
                g = np_img[..., 1].astype(float)
                b = np_img[..., 2].astype(float)
                exg = 2.0 * g - r - b
                foliage_weights = np.clip(exg, 0.0, None)
        except Exception:
            foliage_weights = None

    # Decision logic
    if leak_outside.sum() > 0 and leak_outside.sum() >= canopy_holes.sum():
        ys, xs = np.where(leak_outside)
        idx = len(xs) // 2
        return (int(xs[idx]), int(ys[idx]), False)
    elif canopy_holes.sum() > 0:
        ys, xs = np.where(canopy_holes)
        idx = len(xs) // 2
        return (int(xs[idx]), int(ys[idx]), True)
    elif spurious_noise.sum() > 10 and spurious_noise.sum() > mask_in_box.sum() * 0.4:
        ys, xs = np.where(spurious_noise)
        idx = len(xs) // 2
        return (int(xs[idx]), int(ys[idx]), False)
    elif contour_halo.sum() > 0:
        ys, xs = np.where(contour_halo)
        if foliage_weights is not None:
            halo_weights = foliage_weights * contour_halo
            weights = halo_weights[ys, xs]
            if weights.sum() > 0:
                best_idx = int(np.argmax(weights))
                cx = int(xs[best_idx])
                cy = int(ys[best_idx])
                cx = max(0, min(cx, w - 1))
                cy = max(0, min(cy, h - 1))
                return (cx, cy, True)

        # Select a boundary point along the contour halo band
        idx = len(xs) // 2
        cx = int(xs[idx])
        cy = int(ys[idx])
        cx = max(0, min(cx, w - 1))
        cy = max(0, min(cy, h - 1))
        return (cx, cy, True)
    else:
        ys, xs = np.where(mask_in_box)
        idx = len(xs) // 2
        return (int(xs[idx]), int(ys[idx]), True)


@dataclass
class AblationMetrics:
    """Summary metrics container for an individual ablation experiment."""

    ablation_name: str
    description: str
    num_images: int
    mean_plant_iou: float
    mean_plant_dice: float
    mean_weed_iou: float
    mean_weed_dice: float
    detection_precision: float
    detection_recall: float
    detection_f1: float
    mean_box_iou: float
    mean_pred_chemical_savings_pct: float
    mean_gt_chemical_savings_pct: float
    mean_detection_latency_ms: float
    mean_segmentation_latency_ms: float
    mean_refinement_latency_ms: float
    mean_total_latency_ms: float
    per_crop_metrics: Dict[str, Any] = field(default_factory=dict)
    extra_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return _sanitize_for_json(asdict(self))


class AblationRunner:
    """
    Automated evaluation engine for AgriAgent vision, refinement, and routing ablations.

    Attributes:
        manifest_path: Path to dataset manifest JSON.
        detector: GroundingDINOEngine instance (mock or live).
        segmenter: SAM2Segmenter instance (mock or live).
        mock_mode: Whether running in fast CPU mock mode.
        default_prompt: Zero-shot text prompt for detection.
    """

    def __init__(
        self,
        manifest_path: Union[str, Path] = "data/manifests/eval_manifest_v1.json",
        detector: Optional[GroundingDINOEngine] = None,
        segmenter: Optional[SAM2Segmenter] = None,
        mock_mode: bool = True,
        default_prompt: str = "weed . grass . broadleaf weed .",
    ):
        self.manifest_path = Path(manifest_path)
        self.mock_mode = mock_mode
        self.default_prompt = default_prompt

        self.benchmark_runner = BenchmarkRunner(
            manifest_path=self.manifest_path,
            detector=detector,
            segmenter=segmenter,
            mock_mode=self.mock_mode,
            default_prompt=self.default_prompt,
        )
        self.detector = self.benchmark_runner.detector
        self.segmenter = self.benchmark_runner.segmenter

    def _load_manifest_items(
        self,
        split: Optional[str] = None,
        max_samples: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Load and filter items from the manifest."""
        manifest = self.benchmark_runner.load_manifest()
        items: List[Dict[str, Any]] = manifest.get("items") or manifest.get("images") or []

        if split and split.lower() != "all":
            items = [item for item in items if item.get("split", "").lower() == split.lower()]

        if max_samples is not None and max_samples > 0:
            items = items[:max_samples]

        if not items:
            raise ValueError(
                f"No items found in manifest for split={split}, max_samples={max_samples}"
            )

        return items

    def run_ablation_a(
        self,
        split: Optional[str] = "val",
        max_samples: Optional[int] = None,
    ) -> AblationMetrics:
        """
        Ablation A: Grounding DINO + SAM 2 baseline WITHOUT morphological refinement.

        Evaluates zero-shot detection and initial mask segmentation against verified ground truth.
        """
        logger.info(
            "Executing Ablation A: Baseline without refinement (split=%s, max_samples=%s)...",
            split,
            max_samples,
        )
        items = self._load_manifest_items(split=split, max_samples=max_samples)

        per_image_results = [self.benchmark_runner.evaluate_image(item) for item in items]

        # Aggregate metrics
        total_tp = sum(r.detection_tp for r in per_image_results)
        total_fp = sum(r.detection_fp for r in per_image_results)
        total_fn = sum(r.detection_fn for r in per_image_results)
        precision = float(total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
        recall = float(total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else 0.0
        f1 = (
            float(2 * precision * recall / (precision + recall))
            if (precision + recall) > 0
            else 0.0
        )

        crops = sorted(list(set(r.crop_type for r in per_image_results)))
        per_crop = {}
        for c in crops:
            c_res = [r for r in per_image_results if r.crop_type == c]
            per_crop[c] = {
                "num_images": len(c_res),
                "plant_iou": float(np.mean([r.plant_mask_iou for r in c_res])),
                "weed_iou": float(np.mean([r.weed_mask_iou for r in c_res])),
                "chemical_savings": float(np.mean([r.pred_chemical_savings for r in c_res])),
            }

        return AblationMetrics(
            ablation_name="Ablation A",
            description="Grounding DINO + SAM 2 baseline without morphological refinement",
            num_images=len(per_image_results),
            mean_plant_iou=float(np.mean([r.plant_mask_iou for r in per_image_results])),
            mean_plant_dice=float(np.mean([r.plant_mask_dice for r in per_image_results])),
            mean_weed_iou=float(np.mean([r.weed_mask_iou for r in per_image_results])),
            mean_weed_dice=float(np.mean([r.weed_mask_dice for r in per_image_results])),
            detection_precision=precision,
            detection_recall=recall,
            detection_f1=f1,
            mean_box_iou=float(
                np.mean([r.mean_box_iou for r in per_image_results if r.mean_box_iou > 0] or [0.0])
            ),
            mean_pred_chemical_savings_pct=float(
                np.mean([r.pred_chemical_savings for r in per_image_results])
            ),
            mean_gt_chemical_savings_pct=float(
                np.mean([r.gt_chemical_savings for r in per_image_results])
            ),
            mean_detection_latency_ms=float(
                np.mean([r.detection_latency_ms for r in per_image_results])
            ),
            mean_segmentation_latency_ms=float(
                np.mean([r.segmentation_latency_ms for r in per_image_results])
            ),
            mean_refinement_latency_ms=0.0,
            mean_total_latency_ms=float(np.mean([r.total_latency_ms for r in per_image_results])),
            per_crop_metrics=per_crop,
            extra_details={"refinement_enabled": False, "masks_refined": 0},
        )

    def run_ablation_b(
        self,
        split: Optional[str] = "val",
        max_samples: Optional[int] = None,
        iou_threshold: Optional[float] = None,
    ) -> Tuple[AblationMetrics, Dict[str, float]]:
        """
        Ablation B: Grounding DINO + SAM 2 WITH morphological contour refinement (refinement.py).

        Identifies under-segmented and over-segmented contours, issues corrective point prompts,
        and measures the empirical accuracy delta over baseline Ablation A.

        Returns:
            (ablation_b_metrics, comparison_deltas)
        """
        # In mock mode, mock masks have predicted_iou=0.88; default threshold 0.90 ensures active trigger
        threshold = (
            iou_threshold if iou_threshold is not None else (0.90 if self.mock_mode else 0.85)
        )
        logger.info(
            "Executing Ablation B: With morphological refinement (threshold=%.2f)...", threshold
        )
        items = self._load_manifest_items(split=split, max_samples=max_samples)

        total_masks_count = 0
        refined_masks_count = 0
        refinement_latencies: List[float] = []

        per_image_plant_ious: List[float] = []
        per_image_plant_dices: List[float] = []
        per_image_weed_ious: List[float] = []
        per_image_weed_dices: List[float] = []
        per_image_pred_savings: List[float] = []
        per_image_gt_savings: List[float] = []
        per_image_det_latencies: List[float] = []
        per_image_seg_latencies: List[float] = []
        per_image_tot_latencies: List[float] = []
        matched_box_ious: List[float] = []
        total_tp = 0
        total_fp = 0
        total_fn = 0

        per_crop_data: Dict[str, List[Dict[str, float]]] = {}

        for item in items:
            img_path = self.benchmark_runner.resolve_image_path(item)
            pil_img = Image.open(img_path).convert("RGB")
            width, height = pil_img.size
            crop_type = item.get("crop_type", "unknown")
            gt_annotations = item.get("annotations", [])

            # Detection
            t0 = time.perf_counter()
            pred_boxes: List[Box] = self.detector.detect_to_state_boxes(
                pil_img, text_prompt=self.default_prompt
            )
            t1 = time.perf_counter()
            det_lat = (t1 - t0) * 1000.0

            # Initial SAM 2 Segmentation
            t2 = time.perf_counter()
            raw_masks = self.segmenter.segment_boxes(pil_img, pred_boxes)
            t3 = time.perf_counter()
            seg_lat = (t3 - t2) * 1000.0

            # Morphological Refinement Stage
            t4 = time.perf_counter()
            refined_masks: List[SegmentResult] = []

            for m in raw_masks:
                total_masks_count += 1
                box_coords = (m.box["x1"], m.box["y1"], m.box["x2"], m.box["y2"])
                if should_refine(m.predicted_iou, threshold=threshold):
                    pt = parameterized_error_centroid(m.mask_array, box_coords, image=pil_img)
                    ref_res = self.segmenter.refine_with_point(pil_img, m.box, m.mask_array, pt)
                    refined_masks.append(ref_res)
                    refined_masks_count += 1
                else:
                    refined_masks.append(m)

            t5 = time.perf_counter()
            ref_lat = (t5 - t4) * 1000.0
            refinement_latencies.append(ref_lat)
            tot_lat = (t5 - t0) * 1000.0

            # Ground truth rasterization & evaluation
            gt_weed_mask = rasterize_ground_truth(gt_annotations, width, height, category="weed")
            gt_all_mask = rasterize_ground_truth(gt_annotations, width, height)

            pred_weed_union = np.zeros((height, width), dtype=bool)
            pred_all_union = np.zeros((height, width), dtype=bool)

            for m in refined_masks:
                pred_all_union |= m.mask_array
                lbl = str(m.label).lower()
                if "weed" in lbl or "vegetation" in lbl or "unwanted" in lbl:
                    pred_weed_union |= m.mask_array

            if pred_weed_union.sum() == 0 and pred_all_union.sum() > 0:
                pred_weed_union = pred_all_union.copy()

            plant_iou = compute_iou(pred_all_union, gt_all_mask)
            plant_dice = compute_dice(pred_all_union, gt_all_mask)
            weed_iou = compute_iou(pred_weed_union, gt_weed_mask)
            weed_dice = compute_dice(pred_weed_union, gt_weed_mask)
            pred_savings = compute_herbicide_savings(pred_weed_union, (height, width))
            gt_savings = compute_herbicide_savings(gt_weed_mask, (height, width))

            per_image_plant_ious.append(plant_iou)
            per_image_plant_dices.append(plant_dice)
            per_image_weed_ious.append(weed_iou)
            per_image_weed_dices.append(weed_dice)
            per_image_pred_savings.append(pred_savings)
            per_image_gt_savings.append(gt_savings)
            per_image_det_latencies.append(det_lat)
            per_image_seg_latencies.append(seg_lat)
            per_image_tot_latencies.append(tot_lat)

            # Box metrics
            gt_boxes = [ann["box"] for ann in gt_annotations if "box" in ann]
            matched_gt = set()
            for p_coords in [(b["x1"], b["y1"], b["x2"], b["y2"]) for b in pred_boxes]:
                best_iou = 0.0
                best_g = -1
                for g_idx, g_coords in enumerate(gt_boxes):
                    if g_idx in matched_gt:
                        continue
                    iou = compute_box_iou(p_coords, tuple(g_coords))
                    if iou > best_iou:
                        best_iou = iou
                        best_g = g_idx
                if best_iou >= 0.5 and best_g >= 0:
                    matched_gt.add(best_g)
                    matched_box_ious.append(best_iou)

            tp = len(matched_gt)
            fp = len(pred_boxes) - tp
            fn = len(gt_boxes) - tp
            total_tp += tp
            total_fp += fp
            total_fn += fn

            per_crop_data.setdefault(crop_type, []).append(
                {
                    "plant_iou": plant_iou,
                    "weed_iou": weed_iou,
                    "chemical_savings": pred_savings,
                }
            )

        precision = float(total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
        recall = float(total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else 0.0
        f1 = (
            float(2 * precision * recall / (precision + recall))
            if (precision + recall) > 0
            else 0.0
        )

        per_crop_summary = {
            c: {
                "num_images": len(vals),
                "plant_iou": float(np.mean([v["plant_iou"] for v in vals])),
                "weed_iou": float(np.mean([v["weed_iou"] for v in vals])),
                "chemical_savings": float(np.mean([v["chemical_savings"] for v in vals])),
            }
            for c, vals in per_crop_data.items()
        }

        metrics_b = AblationMetrics(
            ablation_name="Ablation B",
            description="Grounding DINO + SAM 2 with morphological refinement (refinement.py)",
            num_images=len(items),
            mean_plant_iou=float(np.mean(per_image_plant_ious)),
            mean_plant_dice=float(np.mean(per_image_plant_dices)),
            mean_weed_iou=float(np.mean(per_image_weed_ious)),
            mean_weed_dice=float(np.mean(per_image_weed_dices)),
            detection_precision=precision,
            detection_recall=recall,
            detection_f1=f1,
            mean_box_iou=float(np.mean(matched_box_ious) if matched_box_ious else 0.0),
            mean_pred_chemical_savings_pct=float(np.mean(per_image_pred_savings)),
            mean_gt_chemical_savings_pct=float(np.mean(per_image_gt_savings)),
            mean_detection_latency_ms=float(np.mean(per_image_det_latencies)),
            mean_segmentation_latency_ms=float(np.mean(per_image_seg_latencies)),
            mean_refinement_latency_ms=float(np.mean(refinement_latencies)),
            mean_total_latency_ms=float(np.mean(per_image_tot_latencies)),
            per_crop_metrics=per_crop_summary,
            extra_details={
                "refinement_enabled": True,
                "iou_threshold": threshold,
                "total_masks": total_masks_count,
                "masks_refined": refined_masks_count,
                "refinement_rate": float(refined_masks_count / total_masks_count)
                if total_masks_count > 0
                else 0.0,
            },
        )

        # Baseline A metrics for delta comparison
        metrics_a = self.run_ablation_a(split=split, max_samples=max_samples)
        deltas = {
            "delta_plant_iou": round(metrics_b.mean_plant_iou - metrics_a.mean_plant_iou, 6),
            "delta_plant_dice": round(metrics_b.mean_plant_dice - metrics_a.mean_plant_dice, 6),
            "delta_weed_iou": round(metrics_b.mean_weed_iou - metrics_a.mean_weed_iou, 6),
            "delta_weed_dice": round(metrics_b.mean_weed_dice - metrics_a.mean_weed_dice, 6),
            "delta_chemical_savings": round(
                metrics_b.mean_pred_chemical_savings_pct - metrics_a.mean_pred_chemical_savings_pct,
                4,
            ),
            "latency_overhead_ms": round(metrics_b.mean_refinement_latency_ms, 4),
        }

        return metrics_b, deltas

    def run_ablation_c(
        self,
        split: Optional[str] = "val",
        max_samples: Optional[int] = 4,
        sweep_grid: Optional[Dict[str, List[Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Ablation C: Hyperparameter and boundary parameter sweeps.

        Sweeps:
        - iou_threshold: [0.75, 0.85, 0.90]
        - kernel_radius: [1, 2, 3]
        - erosion_iterations: [1, 2]
        - exg_weighting: [True, False]
        """
        logger.info(
            "Executing Ablation C: Parameter sweeps (split=%s, max_samples=%s)...",
            split,
            max_samples,
        )
        items = self._load_manifest_items(split=split, max_samples=max_samples)

        if sweep_grid is None:
            sweep_grid = {
                "iou_threshold": [0.75, 0.85, 0.90],
                "kernel_radius": [1, 2, 3],
                "erosion_iterations": [1, 2],
                "exg_weighting": [True, False],
            }

        # Cache initial detections and segmentations to make parameter sweep fast and pure
        cached_samples: List[Dict[str, Any]] = []
        for item in items:
            img_path = self.benchmark_runner.resolve_image_path(item)
            pil_img = Image.open(img_path).convert("RGB")
            width, height = pil_img.size
            gt_annotations = item.get("annotations", [])

            pred_boxes: List[Box] = self.detector.detect_to_state_boxes(
                pil_img, text_prompt=self.default_prompt
            )
            raw_masks = self.segmenter.segment_boxes(pil_img, pred_boxes)

            gt_weed_mask = rasterize_ground_truth(gt_annotations, width, height, category="weed")
            gt_all_mask = rasterize_ground_truth(gt_annotations, width, height)

            cached_samples.append(
                {
                    "pil_img": pil_img,
                    "width": width,
                    "height": height,
                    "raw_masks": raw_masks,
                    "gt_all_mask": gt_all_mask,
                    "gt_weed_mask": gt_weed_mask,
                }
            )

        sweep_results: List[Dict[str, Any]] = []

        # Iterate through combinations
        for thresh in sweep_grid.get("iou_threshold", [0.85]):
            for radius in sweep_grid.get("kernel_radius", [2]):
                for eros in sweep_grid.get("erosion_iterations", [1]):
                    for exg in sweep_grid.get("exg_weighting", [True]):
                        config_desc = {
                            "iou_threshold": thresh,
                            "kernel_radius": radius,
                            "erosion_iterations": eros,
                            "exg_weighting": exg,
                        }

                        t0 = time.perf_counter()
                        plant_ious: List[float] = []
                        plant_dices: List[float] = []
                        weed_ious: List[float] = []
                        weed_dices: List[float] = []
                        masks_triggered = 0
                        masks_total = 0

                        for sample in cached_samples:
                            pil_img = sample["pil_img"]
                            height, width = sample["height"], sample["width"]
                            pred_all = np.zeros((height, width), dtype=bool)
                            pred_weed = np.zeros((height, width), dtype=bool)

                            for m in sample["raw_masks"]:
                                masks_total += 1
                                box_coords = (m.box["x1"], m.box["y1"], m.box["x2"], m.box["y2"])
                                if m.predicted_iou < thresh:
                                    masks_triggered += 1
                                    pt = parameterized_error_centroid(
                                        m.mask_array,
                                        box_coords,
                                        radius=radius,
                                        erosion_iterations=eros,
                                        exg_weighting=exg,
                                        image=pil_img,
                                    )
                                    ref_res = self.segmenter.refine_with_point(
                                        pil_img, m.box, m.mask_array, pt
                                    )
                                    arr = ref_res.mask_array
                                else:
                                    arr = m.mask_array

                                pred_all |= arr
                                lbl = str(m.label).lower()
                                if "weed" in lbl or "vegetation" in lbl or "unwanted" in lbl:
                                    pred_weed |= arr

                            if pred_weed.sum() == 0 and pred_all.sum() > 0:
                                pred_weed = pred_all.copy()

                            plant_ious.append(compute_iou(pred_all, sample["gt_all_mask"]))
                            plant_dices.append(compute_dice(pred_all, sample["gt_all_mask"]))
                            weed_ious.append(compute_iou(pred_weed, sample["gt_weed_mask"]))
                            weed_dices.append(compute_dice(pred_weed, sample["gt_weed_mask"]))

                        t1 = time.perf_counter()
                        latency_ms = (t1 - t0) * 1000.0

                        sweep_results.append(
                            {
                                "config": config_desc,
                                "mean_plant_iou": float(np.mean(plant_ious)),
                                "mean_plant_dice": float(np.mean(plant_dices)),
                                "mean_weed_iou": float(np.mean(weed_ious)),
                                "mean_weed_dice": float(np.mean(weed_dices)),
                                "refinement_trigger_rate": float(masks_triggered / masks_total)
                                if masks_total > 0
                                else 0.0,
                                "sweep_latency_ms": round(latency_ms, 2),
                            }
                        )

        # Rank configurations by mean plant IoU
        ranked = sorted(sweep_results, key=lambda x: x["mean_plant_iou"], reverse=True)
        best_config = ranked[0] if ranked else {}

        return {
            "num_combinations_evaluated": len(sweep_results),
            "best_config": best_config,
            "all_results": sweep_results,
        }

    def run_ablation_d(
        self,
        num_trials: int = 100,
    ) -> Dict[str, Any]:
        """
        Ablation D: Deterministic rules vs explicitly mocked Clef triage.

        Evaluates:
        - Routing decision accuracy across standardized agricultural test cases.
        - Latency distribution (mean, median, p95, p99, min, max in ms).
        - Action distribution (ACCEPT, REFINE, ESCALATE_SYSTEM2, SUPPRESS_SPRAY).
        """
        logger.info("Executing Ablation D: deterministic vs mock Clef (%d trials)...", num_trials)
        det_router = DeterministicRouter()
        clef_router = ClefFlashRouter(mock_mode=True)

        test_cases: List[Dict[str, Any]] = [
            # 1. Clean high confidence weed
            {
                "case_name": "clean_weed_spot_spray",
                "inputs": {
                    "detection_confidence": 0.94,
                    "predicted_iou": 0.91,
                    "area_pixels": 4500,
                    "label": "weed",
                },
                "expected_action": RouterAction.ACCEPT,
            },
            # 2. Under-segmented mask
            {
                "case_name": "sub_threshold_iou_refine",
                "inputs": {
                    "detection_confidence": 0.88,
                    "predicted_iou": 0.72,
                    "area_pixels": 3200,
                    "iou_threshold": 0.85,
                    "label": "weed",
                },
                "expected_action": RouterAction.REFINE,
            },
            # 3. Species ambiguity
            {
                "case_name": "botanical_species_ambiguity",
                "inputs": {
                    "detection_confidence": 0.85,
                    "predicted_iou": 0.89,
                    "species_ambiguity": True,
                    "label": "unidentified_broadleaf",
                },
                "expected_action": RouterAction.ESCALATE_SYSTEM2,
            },
            # 4. Low detection confidence
            {
                "case_name": "low_detector_confidence",
                "inputs": {
                    "detection_confidence": 0.42,
                    "predicted_iou": 0.88,
                    "min_confidence": 0.70,
                    "label": "weed",
                },
                "expected_action": RouterAction.ESCALATE_SYSTEM2,
            },
            # 5. Severe weed infestation (>85%)
            {
                "case_name": "statutory_safety_infestation_ceiling",
                "inputs": {
                    "detection_confidence": 0.90,
                    "predicted_iou": 0.92,
                    "infestation_pct": 89.2,
                    "max_allowed_infestation": 85.0,
                },
                "expected_action": RouterAction.SUPPRESS_SPRAY,
            },
        ]

        def evaluate_single_router(router: BaseRouter) -> Dict[str, Any]:
            # Warm up
            for case in test_cases[:2]:
                warmup_inputs: Dict[str, Any] = dict(case["inputs"])
                router.route(**warmup_inputs)

            latencies: List[float] = []
            correct_decisions = 0
            total_decisions = 0
            action_counts = {a.value: 0 for a in RouterAction}

            for case in test_cases:
                expected = case["expected_action"]
                inputs: Dict[str, Any] = dict(case["inputs"])
                for _ in range(num_trials):
                    t0 = time.perf_counter_ns()
                    decision = router.route(**inputs)
                    t1 = time.perf_counter_ns()
                    lat_ms = (t1 - t0) / 1_000_000.0
                    latencies.append(lat_ms)

                    total_decisions += 1
                    action_counts[decision.action.value] += 1
                    if decision.action == expected:
                        correct_decisions += 1

            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            p95_idx = int(n * 0.95)
            p99_idx = int(n * 0.99)
            med_idx = int(n * 0.50)

            accuracy = float(correct_decisions / total_decisions) if total_decisions > 0 else 0.0

            return {
                "backend": router.backend.value,
                "total_queries": total_decisions,
                "decision_accuracy": accuracy,
                "mean_latency_ms": float(np.mean(latencies)),
                "median_latency_ms": sorted_lat[med_idx],
                "p95_latency_ms": sorted_lat[p95_idx],
                "p99_latency_ms": sorted_lat[p99_idx],
                "min_latency_ms": sorted_lat[0],
                "max_latency_ms": sorted_lat[-1],
                "action_distribution": action_counts,
            }

        det_stats = evaluate_single_router(det_router)
        clef_stats = evaluate_single_router(clef_router)

        return {
            "deterministic_router": det_stats,
            "clef_flash_mock_router": clef_stats,
            "evaluation_mode": "mock_only; does not measure Clef model behavior or runtime",
        }

    def run_ablation_e(
        self,
        num_trials: int = 50,
    ) -> Dict[str, Any]:
        """
        Ablation E: explicitly mocked local Clef triage contract check.

        Evaluates:
        - Mock contract behavior only; no model latency or vision quality measurement.
        - Deterministic outcomes and suppression behavior in mock mode.
        """
        logger.info("Executing Ablation E: Clef mock contract")
        clef_router = ClefFlashRouter(mock_mode=True)

        synthetic_crop = np.zeros((64, 64, 3), dtype=np.uint8)
        synthetic_crop[16:48, 16:48] = [34, 139, 34]

        # Normal multimodal routing evaluation
        normal_latencies: List[float] = []
        normal_correct = 0
        total_normal = 0

        eval_scenarios: List[Tuple[Dict[str, Any], RouterAction]] = [
            (
                {
                    "detection_confidence": 0.95,
                    "predicted_iou": 0.92,
                    "image_crop": synthetic_crop,
                    "label": "weed",
                },
                RouterAction.ACCEPT,
            ),
            (
                {
                    "detection_confidence": 0.88,
                    "predicted_iou": 0.65,
                    "image_crop": synthetic_crop,
                    "iou_threshold": 0.85,
                },
                RouterAction.REFINE,
            ),
            (
                {
                    "detection_confidence": 0.85,
                    "predicted_iou": 0.90,
                    "species_ambiguity": True,
                    "image_crop": synthetic_crop,
                },
                RouterAction.ESCALATE_SYSTEM2,
            ),
            (
                {
                    "detection_confidence": 0.92,
                    "predicted_iou": 0.90,
                    "infestation_pct": 92.0,
                    "max_allowed_infestation": 85.0,
                },
                RouterAction.SUPPRESS_SPRAY,
            ),
        ]

        for sc_inputs, expected_act in eval_scenarios:
            for _ in range(num_trials):
                t0 = time.perf_counter()
                dec = clef_router.route(**sc_inputs)
                t1 = time.perf_counter()
                normal_latencies.append((t1 - t0) * 1000.0)
                total_normal += 1
                if dec.action == expected_act:
                    normal_correct += 1

        clef_normal_acc = float(normal_correct / total_normal) if total_normal > 0 else 0.0

        return {
            "clef_flash_normal": {
                "multimodal_supported": False,
                "model_parameters": "not loaded; deterministic mock",
                "decision_accuracy": clef_normal_acc,
                "mock_mode": True,
                "mean_latency_ms": float(np.mean(normal_latencies)),
                "min_latency_ms": float(np.min(normal_latencies)),
                "max_latency_ms": float(np.max(normal_latencies)),
            },
            "evaluation_mode": "mock_only; no model runtime, vision capability, network resilience, or live latency measured",
        }

    def run_all_ablations(
        self,
        output_path: Optional[Union[str, Path]] = "data/evaluation_results/ablations_summary.json",
        split: Optional[str] = "val",
        max_samples: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes complete ablation suite (A, B, C, D, E) and writes structured JSON summary.
        """
        logger.info(
            "Starting complete AgriAgent Ablation Suite (split=%s, max_samples=%s)...",
            split,
            max_samples,
        )
        start_time = time.perf_counter()

        metrics_a = self.run_ablation_a(split=split, max_samples=max_samples)
        metrics_b, deltas_ab = self.run_ablation_b(split=split, max_samples=max_samples)
        results_c = self.run_ablation_c(split=split, max_samples=min(max_samples or 10, 4))
        results_d = self.run_ablation_d(num_trials=50)
        results_e = self.run_ablation_e(num_trials=25)

        total_elapsed_s = time.perf_counter() - start_time

        summary_payload = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "manifest_path": str(self.manifest_path),
                "split": split or "all",
                "mock_mode": self.mock_mode,
                "total_runtime_seconds": round(total_elapsed_s, 2),
            },
            "ablation_a": metrics_a.to_dict(),
            "ablation_b": metrics_b.to_dict(),
            "comparison_ab_deltas": deltas_ab,
            "ablation_c": results_c,
            "ablation_d": results_d,
            "ablation_e": results_e,
        }

        sanitized_summary = _sanitize_for_json(summary_payload)

        if output_path is not None:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                json.dump(sanitized_summary, f, indent=2)
            logger.info("Saved ablation summary metrics to: %s", out_p.resolve())

        return sanitized_summary


def main() -> None:
    """CLI entry point for ablation runner."""
    parser = argparse.ArgumentParser(description="AgriAgent Vision & Router Ablation Suite")
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/manifests/eval_manifest_v1.json",
        help="Path to evaluation dataset manifest JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/evaluation_results/ablations_summary.json",
        help="Path to output summary JSON file",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="val",
        help="Manifest split to evaluate ('val', 'test', or 'all')",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum images to evaluate (default: all in split)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live PyTorch deep learning models rather than mock mode",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    runner = AblationRunner(
        manifest_path=args.manifest,
        mock_mode=not args.live,
    )
    results = runner.run_all_ablations(
        output_path=args.output,
        split=args.split,
        max_samples=args.max_samples,
    )

    print("\n" + "=" * 70)
    print("AGRIAGENT ABLATION EVALUATION SUITE COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"Manifest:   {args.manifest}")
    print(f"Output:     {args.output}")
    print(
        f"Ablation A: mPlant IoU = {results['ablation_a']['mean_plant_iou']:.4f}, Latency = {results['ablation_a']['mean_total_latency_ms']:.2f} ms"
    )
    print(
        f"Ablation B: mPlant IoU = {results['ablation_b']['mean_plant_iou']:.4f}, Delta IoU = {results['comparison_ab_deltas']['delta_plant_iou']:+.4f}"
    )
    print("Ablations D and E: mocked router contract checks only; no live model result")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
