"""
src/vision/refinement.py
IoU-based refinement loop. ~30 lines of NumPy.
Inspired by MedSAM-Agent but uses deterministic heuristic instead of RL.
"""
import numpy as np
from typing import List, Tuple, Optional


def compute_error_centroid(
    mask: np.ndarray,
    box: Tuple[float, float, float, float]
) -> Tuple[int, int, bool]:
    """
    Find the point on the mask boundary farthest from the box edge.
    Returns (x, y, is_positive) where is_positive=True means
    the point is INSIDE the mask (under-segmentation) and
    False means OUTSIDE (over-segmentation).
    """
    x1, y1, x2, y2 = [int(v) for v in box]

    # Create box mask for comparison
    h, w = mask.shape
    box_mask = np.zeros((h, w), dtype=bool)
    box_mask[y1:y2, x1:x2] = True

    # Error regions
    under_seg = box_mask & ~mask   # Box region not covered by mask
    over_seg = mask & ~box_mask    # Mask region outside box

    if under_seg.sum() > over_seg.sum():
        # Under-segmentation: add positive point at error centroid
        ys, xs = np.where(under_seg)
        is_positive = True
    else:
        # Over-segmentation: add negative point at error centroid
        ys, xs = np.where(over_seg)
        is_positive = False

    if len(ys) == 0:
        return (int((x1+x2)//2), int((y1+y2)//2), True)

    return (int(xs.mean()), int(ys.mean()), is_positive)


def should_refine(predicted_iou: float, threshold: float = 0.85) -> bool:
    """Check if mask quality is below threshold."""
    return predicted_iou < threshold


def get_refinement_point(
    mask: np.ndarray,
    box: Tuple[float, float, float, float],
    predicted_iou: float,
    threshold: float = 0.85
) -> Optional[Tuple[int, int, bool]]:
    """
    Main refinement function.
    Returns corrective point if IoU is below threshold, else None.
    """
    if not should_refine(predicted_iou, threshold):
        return None
    return compute_error_centroid(mask, box)
