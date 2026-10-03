"""
src/evaluation/iou_dice.py
Compute IoU and Dice coefficient for segmentation evaluation.
"""
import numpy as np
from typing import Dict, List, Tuple


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
    class_names: List[str] = None
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


def compute_herbicide_savings(
    weed_mask: np.ndarray,
    total_image_shape: Tuple[int, int],
    buffer_pixels: int = 10
) -> float:
    """
    Compute herbicide savings percentage.
    savings = 1 - (weed_area + buffer) / total_area
    """
    # Dilate weed mask to add spray buffer safety margin
    try:
        import cv2
        kernel = np.ones((buffer_pixels, buffer_pixels), np.uint8)
        buffered_mask = cv2.dilate(weed_mask.astype(np.uint8), kernel)
    except ImportError:
        # Graceful pure NumPy morphological dilation fallback
        buffered_mask = weed_mask.astype(bool).copy()
        if buffer_pixels > 0:
            h, w = weed_mask.shape
            b = min(buffer_pixels, 20)
            pad_mask = np.pad(buffered_mask, b, mode="constant", constant_values=False)
            dilated = np.zeros_like(buffered_mask)
            for dy in range(2 * b + 1):
                for dx in range(2 * b + 1):
                    dilated |= pad_mask[dy:dy + h, dx:dx + w]
            buffered_mask = dilated

    weed_area = buffered_mask.sum()
    total_area = total_image_shape[0] * total_image_shape[1]

    savings = 1.0 - (weed_area / total_area)
    return max(0.0, min(1.0, savings)) * 100  # Return as percentage
