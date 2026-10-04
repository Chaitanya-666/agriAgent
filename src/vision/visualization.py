"""
src/vision/visualization.py
Visualization utilities for AgriAgent: mask overlays and bounding box annotations.
Part of Week 1 Task 4.1.
"""

from typing import List, Tuple, Union
import numpy as np
from PIL import Image, ImageDraw

try:
    import cv2
except ImportError:
    cv2 = None

from src.state import Box, Mask


# RGB Color Definitions
COLOR_CROP: Tuple[int, int, int] = (0, 255, 0)       # Green
COLOR_WEED: Tuple[int, int, int] = (255, 0, 0)       # Red
COLOR_DISEASE: Tuple[int, int, int] = (255, 255, 0)  # Yellow


def get_label_color(label: str) -> Tuple[int, int, int]:
    """
    Map class label to RGB color:
      - Crop -> Green (0, 255, 0)
      - Weed -> Red (255, 0, 0)
      - Disease -> Yellow (255, 255, 0)
    """
    lbl = (label or "").strip().lower()
    if "weed" in lbl:
        return COLOR_WEED
    elif "disease" in lbl or "blight" in lbl or "pest" in lbl:
        return COLOR_DISEASE
    elif "crop" in lbl or "cotton" in lbl or "plant" in lbl:
        return COLOR_CROP
    return COLOR_WEED


def overlay_masks(
    image: Image.Image,
    masks: List[Mask],
    alpha: float = 0.45,
) -> Image.Image:
    """
    Applies semi-transparent colored overlays for segmented masks using cv2.addWeighted.

    Args:
        image: Source PIL image.
        masks: List of Mask dictionaries containing 'mask_array' and 'label'.
        alpha: Transparency factor for overlay (0.0 = invisible, 1.0 = opaque).

    Returns:
        PIL.Image with blended mask overlays.
    """
    if not masks:
        return image.copy()

    # Convert PIL Image to RGB NumPy array
    img_rgb = np.array(image.convert("RGB"))
    h, w = img_rgb.shape[:2]

    overlay = img_rgb.copy()
    combined_mask = np.zeros((h, w), dtype=bool)

    for m in masks:
        raw_mask = m.get("mask_array")
        if raw_mask is None:
            continue
        mask_arr = np.asarray(raw_mask, dtype=bool)
        if mask_arr.shape != (h, w):
            continue

        color = get_label_color(m.get("label", ""))
        overlay[mask_arr] = color
        combined_mask |= mask_arr

    if not np.any(combined_mask):
        return image.copy()

    # Blend using OpenCV cv2.addWeighted
    if cv2 is not None:
        blended = cv2.addWeighted(overlay, alpha, img_rgb, 1.0 - alpha, 0.0)
    else:
        blended = (
            overlay.astype(np.float32) * alpha + img_rgb.astype(np.float32) * (1.0 - alpha)
        ).astype(np.uint8)

    # Apply blended pixels only to masked regions, leaving background untouched
    result = img_rgb.copy()
    result[combined_mask] = blended[combined_mask]

    return Image.fromarray(result)


def draw_boxes(
    image: Image.Image,
    boxes: List[Box],
) -> Image.Image:
    """
    Draws bounding boxes and label/confidence text on an image.

    Args:
        image: Source PIL image.
        boxes: List of Box dictionaries containing 'x1', 'y1', 'x2', 'y2', 'label', and 'score'.

    Returns:
        PIL.Image with annotated bounding boxes.
    """
    if not boxes:
        return image.copy()

    img_rgb = np.array(image.convert("RGB"))
    h, w = img_rgb.shape[:2]

    if cv2 is not None:
        annotated = img_rgb.copy()
        for b in boxes:
            x1 = max(0, min(w - 1, int(round(b.get("x1", 0)))))
            y1 = max(0, min(h - 1, int(round(b.get("y1", 0)))))
            x2 = max(0, min(w, int(round(b.get("x2", 0)))))
            y2 = max(0, min(h, int(round(b.get("y2", 0)))))

            label = b.get("label", "detection")
            score = float(b.get("score", 0.0))
            color = get_label_color(label)

            # Draw rectangle
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness=2)

            # Prepare text badge
            caption = f"{label} {score:.2f}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            font_thickness = 1
            (tw, th), baseline = cv2.getTextSize(caption, font, font_scale, font_thickness)

            # Determine badge placement
            badge_y1 = max(0, y1 - th - 6)
            badge_y2 = y1 if y1 - th - 6 >= 0 else y1 + th + 6
            badge_x2 = min(w, x1 + tw + 6)

            cv2.rectangle(annotated, (x1, badge_y1), (badge_x2, badge_y2), color, -1)
            text_color = (0, 0, 0) if color == COLOR_DISEASE else (255, 255, 255)
            cv2.putText(
                annotated,
                caption,
                (x1 + 3, badge_y2 - 3),
                font,
                font_scale,
                text_color,
                font_thickness,
                lineType=cv2.LINE_AA,
            )

        return Image.fromarray(annotated)

    # Fallback to PIL ImageDraw if cv2 is not installed
    out_img = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out_img)
    for b in boxes:
        x1 = max(0, min(w - 1, int(round(b.get("x1", 0)))))
        y1 = max(0, min(h - 1, int(round(b.get("y1", 0)))))
        x2 = max(0, min(w, int(round(b.get("x2", 0)))))
        y2 = max(0, min(h, int(round(b.get("y2", 0)))))

        label = b.get("label", "detection")
        score = float(b.get("score", 0.0))
        color = get_label_color(label)

        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        caption = f"{label} {score:.2f}"
        draw.text((x1 + 4, max(0, y1 - 15)), caption, fill=color)

    return out_img
