"""
src/vision/refinement.py
Morphological contour and boundary gradient refinement engine for AgriAgent.

Replaces flawed rectangular bounding-box subtraction with genuine morphological
contour operations, edge boundary gradient refinement, and background soil
negative prompt point generation.

Architecture Rationale:
-----------------------
In precision agricultural vision, weed and crop foliage are organic, non-rectangular
geometries. A bounding box naturally contains background soil in its corners and
inter-row spacing. Naive rectangular box subtraction (bounding-box minus mask) incorrectly tags
background soil as "under-segmented foliage", corrupting SAM 2 prompts.

This module provides:
1. Defensive coordinate normalization (handles inverted, float, negative, or out-of-bound coords).
2. Pure NumPy morphological primitives (dilation, erosion, opening, closing, gradient).
3. Genuine morphological contour refinement (detects concave canopy indentations, holes, and contour boundaries).
4. Dedicated negative prompt point generation for background soil.
5. Invariant protection: all prompt points are guaranteed to lie within image dimensions.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from PIL import Image


def normalize_box_coordinates(
    box: Tuple[float, float, float, float],
    image_shape: Tuple[int, int],
) -> Tuple[int, int, int, int]:
    """
    Defensively normalizes bounding box coordinates.
    
    Guarantees:
    - xmin <= xmax and ymin <= ymax regardless of input order.
    - Floating-point coordinates are safely rounded and converted to int.
    - Clamped strictly within image bounds [0, width] and [0, height].
    
    Args:
        box: (x1, y1, x2, y2) in pixel coordinates.
        image_shape: (height, width) of the target mask/image.
        
    Returns:
        (xmin, ymin, xmax, ymax) as valid bounded integers.
    """
    h, w = image_shape
    x_a, y_a, x_b, y_b = [float(v) for v in box]

    xmin = int(round(min(x_a, x_b)))
    xmax = int(round(max(x_a, x_b)))
    ymin = int(round(min(y_a, y_b)))
    ymax = int(round(max(y_a, y_b)))

    # Clamp to image dimensions
    xmin = max(0, min(xmin, w))
    xmax = max(0, min(xmax, w))
    ymin = max(0, min(ymin, h))
    ymax = max(0, min(ymax, h))

    # Defensive guarantee for degenerate boxes
    if xmax < xmin:
        xmax = xmin
    if ymax < ymin:
        ymax = ymin

    return (xmin, ymin, xmax, ymax)


def binary_dilation(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    """
    Morphological binary dilation using 8-connectivity kernel in pure NumPy.
    Expands the foreground mask outward.
    """
    if radius <= 0 or not np.any(mask):
        return mask.copy()

    out = mask.astype(bool)
    h, w = out.shape
    for _ in range(radius):
        padded = np.pad(out, 1, mode="constant", constant_values=False)
        out = (
            padded[0:h, 0:w] | padded[0:h, 1:w+1] | padded[0:h, 2:w+2] |
            padded[1:h+1, 0:w] | padded[1:h+1, 1:w+1] | padded[1:h+1, 2:w+2] |
            padded[2:h+2, 0:w] | padded[2:h+2, 1:w+1] | padded[2:h+2, 2:w+2]
        )
    return out


def binary_erosion(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    """
    Morphological binary erosion using 8-connectivity kernel in pure NumPy.
    Shrinks the foreground mask inward.
    """
    if radius <= 0 or not np.any(mask):
        return mask.copy()

    out = mask.astype(bool)
    h, w = out.shape
    for _ in range(radius):
        padded = np.pad(out, 1, mode="constant", constant_values=False)
        out = (
            padded[0:h, 0:w] & padded[0:h, 1:w+1] & padded[0:h, 2:w+2] &
            padded[1:h+1, 0:w] & padded[1:h+1, 1:w+1] & padded[1:h+1, 2:w+2] &
            padded[2:h+2, 0:w] & padded[2:h+2, 1:w+1] & padded[2:h+2, 2:w+2]
        )
    return out


def binary_closing(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    """
    Morphological binary closing (dilation followed by erosion).
    Fills internal holes and concave indentations within the foliage canopy.
    """
    return binary_erosion(binary_dilation(mask, radius), radius)


def binary_opening(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    """
    Morphological binary opening (erosion followed by dilation).
    Eliminates thin background protrusions, spidery artifacts, and isolated noise.
    """
    return binary_dilation(binary_erosion(mask, radius), radius)


def morphological_gradient(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    """
    Computes morphological gradient (dilation XOR erosion).
    Yields the precise boundary contour ring of the foliage.
    """
    dilated = binary_dilation(mask, radius)
    eroded = binary_erosion(mask, radius)
    return dilated & ~eroded


def compute_error_centroid(
    mask: np.ndarray,
    box: Tuple[float, float, float, float],
    image: Optional[Union[np.ndarray, Image.Image]] = None,
) -> Tuple[int, int, bool]:
    """
    Morphological contour/boundary gradient refinement.
    
    Identifies boundary regions that genuinely belong to the foliage contour
    rather than naive rectangular box subtraction.
    
    Returns:
        (x, y, is_positive):
            - is_positive=True: Under-segmented foliage region (canopy gap or boundary contour).
            - is_positive=False: Over-segmented background leakage (spillover outside box or soil artifact).
    """
    h, w = mask.shape
    xmin, ymin, xmax, ymax = normalize_box_coordinates(box, (h, w))

    # Box binary mask
    box_mask = np.zeros((h, w), dtype=bool)
    box_mask[ymin:ymax, xmin:xmax] = True

    # Sub-mask within the bounding box
    mask_in_box = mask & box_mask

    # 1. Total under-segmentation failure (mask completely empty inside box)
    if mask_in_box.sum() == 0:
        cx = int((xmin + xmax) // 2) if xmax > xmin else min(xmin, w - 1)
        cy = int((ymin + ymax) // 2) if ymax > ymin else min(ymin, h - 1)
        return (cx, cy, True)

    # 2. Check for over-segmentation leakage outside the bounding box
    leak_outside = mask & ~box_mask
    spurious_noise = (mask & ~binary_opening(mask, radius=2)) & box_mask

    # 3. Check for under-segmentation within the foliage canopy contour
    # Canopy indentations and internal gaps
    closed_mask = binary_closing(mask, radius=3)
    canopy_holes = (closed_mask & ~mask) & box_mask

    # Morphological boundary halo (contour edge gradient band)
    dilated_mask = binary_dilation(mask, radius=2)
    contour_halo = (dilated_mask & ~mask) & box_mask

    # 4. Integrate image vegetation index (Excess Green: 2G - R - B) if image available
    foliage_gradient_weights: Optional[np.ndarray] = None
    if image is not None:
        try:
            if isinstance(image, Image.Image):
                np_img = np.array(image.convert("RGB"))
            elif isinstance(image, np.ndarray):
                np_img = image if image.ndim == 3 else np.stack([image]*3, axis=-1)
            else:
                np_img = None

            if np_img is not None and np_img.shape[:2] == (h, w):
                r = np_img[..., 0].astype(float)
                g = np_img[..., 1].astype(float)
                b = np_img[..., 2].astype(float)
                # Excess green index: ExG = 2G - R - B
                exg = 2.0 * g - r - b
                # High ExG indicates genuine plant tissue
                foliage_gradient_weights = np.clip(exg, 0, None)
        except Exception:
            foliage_gradient_weights = None

    # Decision: Over-segmentation vs Under-segmentation
    # If the mask noticeably spills outside the box, over-segmentation must be penalized
    if leak_outside.sum() > 0 and leak_outside.sum() >= canopy_holes.sum():
        ys, xs = np.where(leak_outside)
        is_positive = False
    elif canopy_holes.sum() > 0:
        # Canopy has internal gaps or concave contour bay missing
        ys, xs = np.where(canopy_holes)
        is_positive = True
    elif spurious_noise.sum() > 10 and spurious_noise.sum() > mask_in_box.sum() * 0.4:
        ys, xs = np.where(spurious_noise)
        is_positive = False
    elif contour_halo.sum() > 0:
        # Foliage boundary expansion along morphological gradient
        if foliage_gradient_weights is not None:
            halo_weights = foliage_gradient_weights * contour_halo
            if halo_weights.sum() > 0:
                ys, xs = np.where(contour_halo)
                weights = halo_weights[ys, xs]
                if weights.sum() > 0:
                    cx = int(round(np.average(xs, weights=weights)))
                    cy = int(round(np.average(ys, weights=weights)))
                    cx = max(0, min(cx, w - 1))
                    cy = max(0, min(cy, h - 1))
                    return (cx, cy, True)

        ys, xs = np.where(contour_halo)
        is_positive = True
    else:
        # Fallback to mask centroid
        ys, xs = np.where(mask_in_box)
        is_positive = True

    if len(ys) == 0:
        cx = int((xmin + xmax) // 2) if xmax > xmin else min(xmin, w - 1)
        cy = int((ymin + ymax) // 2) if ymax > ymin else min(ymin, h - 1)
        return (cx, cy, True)

    cx = int(round(float(xs.mean())))
    cy = int(round(float(ys.mean())))

    # Invariant clamp
    cx = max(0, min(cx, w - 1))
    cy = max(0, min(cy, h - 1))

    return (cx, cy, is_positive)


def get_negative_prompt_points(
    mask: np.ndarray,
    box: Tuple[float, float, float, float],
    count: int = 1,
    image: Optional[Union[np.ndarray, Image.Image]] = None,
) -> List[Tuple[int, int, bool]]:
    """
    Selects negative prompt points on background soil.
    
    Identifies background soil safely separated from the foliage contour
    to constrain SAM 2 against over-segmentation and background leakage.
    
    Returns:
        List of (x, y, False) negative prompt coordinates.
    """
    h, w = mask.shape
    xmin, ymin, xmax, ymax = normalize_box_coordinates(box, (h, w))

    box_mask = np.zeros((h, w), dtype=bool)
    box_mask[ymin:ymax, xmin:xmax] = True

    # Buffer zone around foliage (4-pixel safety perimeter)
    dilated_foliage = binary_dilation(mask, radius=4)

    # Background soil candidate inside bounding box
    background_soil = box_mask & ~dilated_foliage

    # If image provided, prefer pixels with non-plant color (low Excess Green)
    if image is not None and background_soil.sum() > 0:
        try:
            if isinstance(image, Image.Image):
                np_img = np.array(image.convert("RGB"))
            elif isinstance(image, np.ndarray):
                np_img = image if image.ndim == 3 else np.stack([image]*3, axis=-1)
            else:
                np_img = None

            if np_img is not None and np_img.shape[:2] == (h, w):
                r = np_img[..., 0].astype(float)
                g = np_img[..., 1].astype(float)
                b = np_img[..., 2].astype(float)
                exg = 2.0 * g - r - b
                soil_confidence = np.clip(-exg, 0, None)
                soil_weights = soil_confidence * background_soil
                if soil_weights.sum() > 0:
                    ys, xs = np.where(background_soil)
                    weights = soil_weights[ys, xs]
                    if weights.sum() > 0:
                        weights /= weights.sum()
                        chosen_indices = np.random.choice(len(xs), size=min(count, len(xs)), replace=False, p=weights)
                        return [(int(xs[idx]), int(ys[idx]), False) for idx in chosen_indices]
        except Exception:
            pass

    ys, xs = np.where(background_soil)
    if len(ys) == 0:
        # Fallback to corners of bounding box if outside foliage
        cx_min = max(0, min(xmin, w - 1))
        cy_min = max(0, min(ymin, h - 1))
        cx_max = max(0, min(xmax - 1, w - 1))
        cy_max = max(0, min(ymax - 1, h - 1))
        corners = [
            (cx_min, cy_min),
            (cx_max, cy_min),
            (cx_min, cy_max),
            (cx_max, cy_max),
        ]
        valid_corners = [
            (cx, cy, False) for cx, cy in corners
            if not mask[cy, cx]
        ]
        if valid_corners:
            return valid_corners[:count]
        # Return outside box point if safe
        return [(cx_min, cy_min, False)]

    # Deterministically select representative soil points spread across background
    indices = np.linspace(0, len(xs) - 1, min(count, len(xs)), dtype=int)
    points = []
    for idx in indices:
        cx = max(0, min(int(xs[idx]), w - 1))
        cy = max(0, min(int(ys[idx]), h - 1))
        points.append((cx, cy, False))

    return points


def should_refine(predicted_iou: float, threshold: float = 0.85) -> bool:
    """Check if mask quality is below the active refinement threshold."""
    return float(predicted_iou) < float(threshold)


def get_refinement_point(
    mask: np.ndarray,
    box: Tuple[float, float, float, float],
    predicted_iou: float,
    threshold: float = 0.85,
    image: Optional[Union[np.ndarray, Image.Image]] = None,
) -> Optional[Tuple[int, int, bool]]:
    """
    Main refinement interface for System-1 workflow.
    
    Returns corrective point prompt if IoU is below threshold, else None.
    """
    if not should_refine(predicted_iou, threshold):
        return None
    return compute_error_centroid(mask, box, image=image)


def generate_refinement_points(
    mask: np.ndarray,
    box: Tuple[float, float, float, float],
    predicted_iou: float,
    threshold: float = 0.85,
    num_positive: int = 1,
    num_negative: int = 1,
    image: Optional[Union[np.ndarray, Image.Image]] = None,
) -> Dict[str, Any]:
    """
    Comprehensive refinement point generator producing paired positive foliage
    prompts and negative background soil prompts.
    """
    if not should_refine(predicted_iou, threshold):
        return {
            "needs_refine": False,
            "positive_points": [],
            "negative_points": [],
            "all_points": [],
        }

    positive_pt = compute_error_centroid(mask, box, image=image)
    pos_points = [positive_pt] if positive_pt[2] else []
    neg_points = get_negative_prompt_points(mask, box, count=num_negative, image=image)

    # If error centroid itself was negative (over-segmentation)
    if not positive_pt[2]:
        neg_points.insert(0, positive_pt)

    all_points = pos_points + neg_points
    return {
        "needs_refine": True,
        "positive_points": pos_points,
        "negative_points": neg_points,
        "all_points": all_points,
    }
