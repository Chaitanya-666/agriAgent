"""
src/vision/plant_candidates.py
Rule-based crop/weed classification of every green plant in a photo.

Grounding DINO rarely proposes the small weeds (in the sugar beet set it boxes mostly the large
crop plants), so its boxes cannot be the only candidates. Here every connected patch of
vegetation (excess green above a per-image Otsu threshold) is a candidate, and plain rules decide:

1. crop    if at least 30% of the patch lies inside a crop-labelled SAM 2 mask;
2. crop    if the photo shows clear rows and the patch lies on the densest band (conservative:
           a weed inside the row is missed rather than a crop plant sprayed);
3. weed    if the photo has crop masks and the patch is smaller than a quarter of the median
           crop plant in the same photo (self-calibrating: no threshold is tuned on labels);
4. weed    if the photo shows clear rows and the patch lies off the band;
5. unsure  otherwise (never sprayed).

Leaves of one plant often separate in the vegetation map, so small gaps are closed first
(a square of about 1% of the image side) before patches are found.

Known bias: rule 3 relies on weeds being smaller than the crop, true for young sugar beet,
false for the cotton close-ups where a single large weed fills the photo.
Known limitation: the row test does not require several plants, so a lone plant forms a "row"
and is protected as crop (safe, but it is never called a weed). Rules frozen as "v3" after the
one-time held-out test (docs/results/plant_rules_v3_*.md).
"""

from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.evaluation.crop_protection import vegetation_mask

CROP_OVERLAP = 0.3
SMALL_VS_CROP = 0.25
MIN_PATCH_PX = 12
WORK_LONG_SIDE = 1024


def connected_components(mask: np.ndarray) -> Tuple[np.ndarray, int]:
    """Label 8-connected regions; OpenCV when installed, otherwise a breadth-first search."""
    try:
        import cv2

        count, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
        return labels, count - 1
    except ImportError:
        labels = np.zeros(mask.shape, dtype=np.int32)
        h, w = mask.shape
        count = 0
        for y, x in zip(*np.nonzero(mask)):
            if labels[y, x]:
                continue
            count += 1
            labels[y, x] = count
            queue = deque([(y, x)])
            while queue:
                cy, cx = queue.popleft()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                            labels[ny, nx] = count
                            queue.append((ny, nx))
        return labels, count


def close_gaps(mask: np.ndarray, radius: int) -> np.ndarray:
    """Morphological closing with a square of side 2 * radius + 1 (joins leaves of one plant)."""
    from src.evaluation.iou_dice import spray_footprint

    grown = spray_footprint(mask, radius)
    return ~spray_footprint(~grown, radius)


def row_profile(vegetation: np.ndarray, min_peakiness: float = 2.0) -> Optional[Tuple[str, np.ndarray]]:
    """Orientation and smoothed vegetation profile of the crop rows, or None without clear rows."""
    best = None
    for axis, orientation in ((1, "horizontal"), (0, "vertical")):
        profile = np.convolve(vegetation.sum(axis=axis), np.ones(15) / 15, mode="same")
        peakiness = profile.max() / (profile.mean() + 1e-6)
        if best is None or peakiness > best[0]:
            best = (peakiness, orientation, profile)
    assert best is not None
    return None if best[0] < min_peakiness else (best[1], best[2])


def classify_plants(
    image_rgb: np.ndarray, crop_masks: List[np.ndarray]
) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    """
    Returns (weed_mask, crop_mask, patches) at the image's full resolution. crop_masks are
    SAM 2 masks whose label names the crop (whole-photo masks already removed).
    """
    full_h, full_w = image_rgb.shape[:2]
    step = max(1, int(np.ceil(max(full_h, full_w) / WORK_LONG_SIDE)))
    small = image_rgb[::step, ::step]
    vegetation = vegetation_mask(small)
    crop_ref = np.zeros(vegetation.shape, dtype=bool)
    crop_sizes = []
    for mask in crop_masks:
        m = np.asarray(mask, dtype=bool)[::step, ::step][: vegetation.shape[0], : vegetation.shape[1]]
        crop_ref |= m
        size = int((m & vegetation).sum())
        if size:
            crop_sizes.append(size)
    median_crop = float(np.median(crop_sizes)) if crop_sizes else None
    rows = row_profile(vegetation)

    labels, count = connected_components(close_gaps(vegetation, max(1, round(0.01 * max(vegetation.shape)))))
    labels = np.where(vegetation, labels, 0)  # patches keep only real vegetation pixels
    weed = np.zeros(vegetation.shape, dtype=bool)
    crop = np.zeros(vegetation.shape, dtype=bool)
    patches = []
    for index in range(1, count + 1):
        patch = labels == index
        area = int(patch.sum())
        if area < MIN_PATCH_PX:
            continue
        overlap = float((patch & crop_ref).sum()) / area
        on_row = None
        if rows is not None:
            orientation, profile = rows
            ys, xs = np.nonzero(patch)
            centre = ys.mean() if orientation == "horizontal" else xs.mean()
            on_row = bool(profile[int(centre)] >= 0.5 * profile.max())
        if overlap >= CROP_OVERLAP:
            verdict, why = "crop", f"{overlap:.0%} inside a crop mask"
        elif on_row:
            verdict, why = "crop", "on the crop row"
        elif median_crop is not None:
            small_patch = area < SMALL_VS_CROP * median_crop
            verdict = "weed" if small_patch else "unsure"
            why = f"{area} px vs median crop plant {median_crop:.0f} px"
        elif on_row is False:
            verdict, why = "weed", "off the crop row"
        else:
            verdict, why = "unsure", "no crop masks and no clear rows"
        (weed if verdict == "weed" else crop if verdict == "crop" else np.zeros_like(weed))[patch] = True
        patches.append({"area_px": area * step * step, "verdict": verdict, "why": why})

    def full(mask: np.ndarray) -> np.ndarray:
        return np.repeat(np.repeat(mask, step, axis=0), step, axis=1)[:full_h, :full_w]

    return full(weed), full(crop), patches
