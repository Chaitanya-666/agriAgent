"""Evaluation metrics for segmentation and detection."""

from src.evaluation.iou_dice import (
    compute_iou,
    compute_dice,
    evaluate_batch,
    compute_herbicide_savings,
)

# Friendly aliases
calculate_iou = compute_iou
calculate_dice = compute_dice
evaluate_batch_segmentation = evaluate_batch

__all__ = [
    "compute_iou",
    "compute_dice",
    "evaluate_batch",
    "compute_herbicide_savings",
    "calculate_iou",
    "calculate_dice",
    "evaluate_batch_segmentation",
]
