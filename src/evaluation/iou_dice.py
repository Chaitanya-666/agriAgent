"""
src/evaluation/iou_dice.py
Compute IoU and Dice coefficient for segmentation evaluation.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple


def compute_iou(prediction: np.ndarray, ground_truth: np.ndarray) -> float:
    """Compute Intersection over Union between two binary masks."""
    intersection = np.logical_and(prediction, ground_truth).sum()
    union = np.logical_or(prediction, ground_truth).sum()
    if union == 0:
        return 1.0 if intersection == 0 else 0.0
    return float(intersection / union)


def compute_dice(prediction: np.ndarray, ground_truth: np.ndarray) -> float:
    """Compute Dice coefficient between two binary masks."""
    intersection = np.logical_and(prediction, ground_truth).sum()
    total = prediction.sum() + ground_truth.sum()
    if total == 0:
        return 1.0
    return float(2 * intersection / total)


def evaluate_batch(
    predictions: List[np.ndarray],
    ground_truths: List[np.ndarray],
    class_names: Optional[List[str]] = None
) -> Dict[str, float]:
    """Compute mean IoU and Dice over a batch of masks."""
    ious = []
    dices = []

    for pred, gt in zip(predictions, ground_truths):
        ious.append(compute_iou(pred, gt))
        dices.append(compute_dice(pred, gt))

    results = {
        "mean_iou": float(np.mean(ious)),
        "std_iou": float(np.std(ious)),
        "mean_dice": float(np.mean(dices)),
        "std_dice": float(np.std(dices)),
        "num_samples": len(ious),
        "ci_95_iou": float(1.96 * np.std(ious) / np.sqrt(len(ious))),
        "ci_95_dice": float(1.96 * np.std(dices) / np.sqrt(len(dices))),
    }
    return results


def spray_footprint(mask: np.ndarray, buffer_pixels: int = 10) -> np.ndarray:
    """
    Area a nozzle actually covers: the mask grown by buffer_pixels on every side.

    Uses a square of side 2 * buffer_pixels + 1 with or without OpenCV, so the result no
    longer depends on what is installed (known issue K10: OpenCV used a square of side
    buffer_pixels, the NumPy fallback one of side 2 * buffer_pixels + 1).
    """
    binary = np.asarray(mask, dtype=bool)
    if buffer_pixels <= 0:
        return binary.copy()
    side = 2 * buffer_pixels + 1
    try:
        import cv2

        return cv2.dilate(binary.astype(np.uint8), np.ones((side, side), np.uint8)).astype(bool)
    except ImportError:
        # Separable dilation: grow along rows, then along columns.
        grown = binary.copy()
        for axis in (0, 1):
            padded = np.pad(grown, [(buffer_pixels, buffer_pixels) if a == axis else (0, 0) for a in (0, 1)])
            length = grown.shape[axis]
            grown = np.zeros_like(grown)
            for offset in range(side):
                window = padded[offset : offset + length] if axis == 0 else padded[:, offset : offset + length]
                grown |= window
        return grown


def compute_herbicide_savings(
    weed_mask: np.ndarray,
    total_image_shape: Tuple[int, int],
    buffer_pixels: int = 10
) -> float:
    """
    Herbicide saved compared with spraying the whole image, in percent:
    100 * (1 - sprayed area / image area), where the sprayed area is spray_footprint().
    """
    sprayed_area = spray_footprint(weed_mask, buffer_pixels).sum()
    total_area = total_image_shape[0] * total_image_shape[1]
    savings = 1.0 - (sprayed_area / total_area)
    return max(0.0, min(1.0, savings)) * 100  # Return as percentage
