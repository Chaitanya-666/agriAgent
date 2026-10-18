"""
src/evaluation/crop_protection.py
Spray-map metrics against box labels: how much crop is sprayed and how much weed is hit.

The evaluation labels (eval_manifest_v2) are boxes, and a box also contains soil. Plant pixels
are therefore estimated as the vegetation inside each box: excess green (2G - R - B) above a
threshold chosen per image with Otsu's method, because soil colour differs between fields.
A pixel inside both a crop box and a weed box counts as crop (the conservative choice for
crop protection) and is left out of the weed pixels.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    """Threshold that best separates the values into two groups (Otsu's method)."""
    hist, edges = np.histogram(values, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2
    weight = np.cumsum(hist)
    cumulative_mean = np.cumsum(hist * centres)
    total_weight, total_mean = weight[-1], cumulative_mean[-1]
    between = (total_mean * weight - cumulative_mean * total_weight) ** 2 / (
        weight * (total_weight - weight) + 1e-9
    )
    return float(centres[np.argmax(between[:-1])])


def vegetation_mask(image_rgb: np.ndarray) -> np.ndarray:
    """Green-plant pixels of an RGB image (H, W, 3) by excess green and Otsu's threshold."""
    rgb = np.asarray(image_rgb, dtype=float)[..., :3]
    excess_green = 2 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]
    return excess_green > otsu_threshold(excess_green)


def _box_mask(box: List[float], shape: Tuple[int, int]) -> np.ndarray:
    height, width = shape
    x1, y1, x2, y2 = box
    mask = np.zeros(shape, dtype=bool)
    mask[max(0, int(np.floor(y1))) : min(height, int(np.ceil(y2))),
         max(0, int(np.floor(x1))) : min(width, int(np.ceil(x2)))] = True
    return mask


def ground_truth_masks(
    annotations: List[Dict[str, Any]], vegetation: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
    """
    Plant pixels per category from box annotations.

    Returns (crop_pixels, weed_pixels, crop_objects, weed_objects): the union masks and one
    mask per labelled plant (vegetation inside its box).
    """
    shape = vegetation.shape
    crop_objects: List[np.ndarray] = []
    weed_objects: List[np.ndarray] = []
    for ann in annotations:
        plant = _box_mask(ann["box"], shape) & vegetation
        (crop_objects if ann["category"] == "crop" else weed_objects).append(plant)
    crop = np.zeros(shape, dtype=bool)
    for plant in crop_objects:
        crop |= plant
    weed = np.zeros(shape, dtype=bool)
    for plant in weed_objects:
        weed |= plant
    weed &= ~crop
    return crop, weed, crop_objects, [plant & ~crop for plant in weed_objects]


def _percent(part: int, whole: int) -> Optional[float]:
    return None if whole == 0 else round(100.0 * part / whole, 2)


def spray_metrics(
    sprayed: np.ndarray,
    crop_pixels: np.ndarray,
    weed_pixels: np.ndarray,
    crop_objects: Optional[List[np.ndarray]] = None,
    weed_objects: Optional[List[np.ndarray]] = None,
    object_hit_fraction: float = 0.5,
) -> Dict[str, Any]:
    """
    Compare a spray map with the plant pixels of each category.

    crop_sprayed_pct: crop pixels sprayed / all crop pixels (lower is better, None without crop).
    weed_recall_pct:  weed pixels sprayed / all weed pixels (higher is better, None without weeds).
    savings_pct:      100 * (1 - sprayed pixels / image pixels).
    Object counts: a weed counts as hit when at least object_hit_fraction of its pixels are
    sprayed; a crop plant counts as damaged when any of its pixels is sprayed.
    """
    sprayed = np.asarray(sprayed, dtype=bool)
    crop_total, weed_total = int(crop_pixels.sum()), int(weed_pixels.sum())
    crop_hit, weed_hit = int((sprayed & crop_pixels).sum()), int((sprayed & weed_pixels).sum())
    result: Dict[str, Any] = {
        "crop_pixels": crop_total,
        "crop_pixels_sprayed": crop_hit,
        "crop_sprayed_pct": _percent(crop_hit, crop_total),
        "weed_pixels": weed_total,
        "weed_pixels_sprayed": weed_hit,
        "weed_recall_pct": _percent(weed_hit, weed_total),
        "sprayed_pct": round(100.0 * sprayed.sum() / sprayed.size, 2),
        "savings_pct": round(100.0 * (1 - sprayed.sum() / sprayed.size), 2),
    }
    if crop_objects is not None:
        plants = [p for p in crop_objects if p.any()]
        result["crop_plants"] = len(plants)
        result["crop_plants_damaged"] = sum(bool((p & sprayed).any()) for p in plants)
    if weed_objects is not None:
        plants = [p for p in weed_objects if p.any()]
        result["weed_plants"] = len(plants)
        result["weed_plants_hit"] = sum(
            bool((p & sprayed).sum() >= object_hit_fraction * p.sum()) for p in plants
        )
    return result
