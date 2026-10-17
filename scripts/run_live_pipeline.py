"""
scripts/run_live_pipeline.py
Standalone Execution Script for AgriAgent Grounded-SAM 2 Vision Pipeline.

Usage:
------
# 1. Run live on GPU (loads real HuggingFace weights on Colab/Kaggle/Workstation):
python scripts/run_live_pipeline.py --image path/to/field.jpg

# 2. Run with custom detection prompt:
python scripts/run_live_pipeline.py --image field.jpg --prompt "cotton weed . broadleaf plant ."

# 3. Force mock mode on lightweight CPU laptops:
python scripts/run_live_pipeline.py --mock
"""

import argparse
import logging
from pathlib import Path
import sys
import numpy as np
from PIL import Image

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.workflow import VisionWorkflowRunner, create_initial_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agriagent.live")


def create_synthetic_field_image(width: int = 640, height: int = 480) -> Image.Image:
    """Creates a high-contrast agricultural field image with soil and weed patches for testing."""
    # Soil background (brownish-tan)
    arr = np.full((height, width, 3), (120, 95, 65), dtype=np.uint8)

    # Add random soil grain texture
    noise = np.random.randint(-15, 15, (height, width, 3), dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Draw simulated crop rows (dark green)
    for x in range(80, width, 160):
        arr[:, max(0, x - 25):min(width, x + 25)] = [50, 110, 40]

    # Draw simulated weed patches (bright lime green)
    weed_centers = [(180, 160, 35), (380, 240, 45), (260, 380, 30)]
    for wx, wy, rad in weed_centers:
        yy, xx = np.ogrid[max(0, wy - rad):min(height, wy + rad), max(0, wx - rad):min(width, wx + rad)]
        circle = ((xx - wx) ** 2 + ((yy - wy) ** 2)) <= rad ** 2
        arr[max(0, wy - rad):min(height, wy + rad), max(0, wx - rad):min(width, wx + rad)][circle] = [90, 195, 55]

    return Image.fromarray(arr)


def approved_spray_mask(state: dict, height: int, width: int) -> np.ndarray:
    """The spray map the safety gate actually approved (not every SAM 2 mask)."""
    artifact = (state.get("artifacts") or {}).get("spray_map")
    payload = getattr(artifact, "payload", None) or {}
    composite = payload.get("composite_mask")
    if composite is None:
        return np.zeros((height, width), dtype=bool)
    return np.asarray(composite, dtype=bool)


def plot_and_save_results(
    image: Image.Image,
    state: dict,
    output_path: str = "output_spray_map.png"
) -> None:
    """Saves a 4-panel figure: original, DINO boxes, all SAM 2 masks by label, gated spray map."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError:
        logger.warning("Matplotlib not installed. Skipping plot visualization.")
        return

    np_img = np.array(image)
    boxes = state.get("boxes", [])
    masks = state.get("masks", [])
    spray_info = state.get("spray_map", {})
    h, w = np_img.shape[:2]

    fig, axes = plt.subplots(1, 4, figsize=(24, 6))

    # Panel 1: Raw Field Photo
    axes[0].imshow(np_img)
    axes[0].set_title("1. Original", fontsize=12, fontweight="bold")
    axes[0].axis("off")

    # Panel 2: Grounding DINO Bounding Boxes
    axes[1].imshow(np_img)
    axes[1].set_title(f"2. Grounding DINO ({len(boxes)} Detections)", fontsize=12, fontweight="bold")
    axes[1].axis("off")
    for b in boxes:
        x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
        rect = patches.Rectangle(
            (x1, y1), x2 - x1, y2 - y1,
            linewidth=2, edgecolor="red", facecolor="none", linestyle="--"
        )
        axes[1].add_patch(rect)
        axes[1].text(
            x1, max(0, y1 - 6),
            f"{b['label']} ({b['score']:.2f})",
            color="white", fontsize=9, fontweight="bold",
            bbox=dict(facecolor="red", alpha=0.7, edgecolor="none", pad=2)
        )

    # Panel 3: every SAM 2 mask, coloured by its label (red = weed label, blue = anything else)
    overlay = np_img.copy()
    for m in masks:
        is_weed_label = "weed" in str(m.get("label", "")).lower()
        overlay[m["mask_array"]] = [220, 30, 30] if is_weed_label else [30, 90, 220]
    axes[2].imshow((0.55 * np_img + 0.45 * overlay).astype(np.uint8))
    axes[2].set_title(
        f"3. SAM 2 masks ({len(masks)})\nred = weed label, blue = other label",
        fontsize=12, fontweight="bold",
    )
    axes[2].axis("off")

    # Panel 4: what the safety gate approved for spraying
    sprayed = approved_spray_mask(state, h, w)
    overlay = np_img.copy()
    overlay[sprayed] = [220, 30, 30]
    axes[3].imshow((0.55 * np_img + 0.45 * overlay).astype(np.uint8))
    savings = spray_info.get("chemical_savings_percentage", 0.0)
    infest = spray_info.get("infestation_percentage", 0.0)
    axes[3].set_title(
        f"4. Gated spray map\n[Sprayed: {infest}% | Savings: {savings:.1f}%]",
        fontsize=12, fontweight="bold", color="darkgreen"
    )
    axes[3].axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    logger.info("Saved 4-panel visualization to: %s", output_path)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Run AgriAgent Grounded-SAM 2 Pipeline")
    parser.add_argument("--image", type=str, default=None, help="Path to input image file")
    parser.add_argument("--prompt", type=str, default="cotton weed . broadleaf plant .", help="Detection prompt")
    parser.add_argument("--mock", action="store_true", help="Force mock mode even if GPU/PyTorch are available")
    parser.add_argument("--output", type=str, default="output_spray_map.png", help="Output visualization path")
    args = parser.parse_args()

    # 1. Load or synthesize test image
    if args.image and not Path(args.image).exists():
        sys.exit(f"Image not found: {args.image}")
    if args.image:
        logger.info("Loading image from disk: %s", args.image)
        img = Image.open(args.image).convert("RGB")
    else:
        logger.info("No image provided. Generating synthetic agricultural cotton field patch...")
        img = create_synthetic_field_image(640, 480)

    # 2. Initialize Pipeline
    logger.info("Initializing AgriAgent System-1 (mock_mode=%s)...", args.mock)
    runner = VisionWorkflowRunner(mock_mode=args.mock, iou_threshold=0.85)

    # 3. Execute
    initial_state = create_initial_state(img, text_prompt=args.prompt)
    logger.info("Executing pipeline on prompt: '%s'", args.prompt)
    final_state = runner.run(initial_state)

    # 4. Display Results
    detector_mode = "MOCK" if runner.detector.mock_mode else "REAL"
    segmenter_mode = "MOCK" if runner.segmenter.mock_mode else "REAL"
    print("\n" + "=" * 65)
    print("🌾 AGRIAGENT SYSTEM-1 REFLEX RESULTS")
    print("=" * 65)
    print(f"• MODE USED                : detector={detector_mode}, segmenter={segmenter_mode}")
    print(f"• Candidate Bounding Boxes : {len(final_state['boxes'])}")
    for i, b in enumerate(final_state["boxes"], 1):
        print(f"  [{i}] {b['label']} (conf: {b['score']:.2f}) -> [{b['x1']:.1f}, {b['y1']:.1f}, {b['x2']:.1f}, {b['y2']:.1f}]")

    h, w = img.size[1], img.size[0]
    sprayed = approved_spray_mask(final_state, h, w)
    print(f"\n• Segmented Instance Masks : {len(final_state['masks'])}")
    for i, m in enumerate(final_state["masks"], 1):
        on_map = "SPRAYED" if (m["mask_array"] & sprayed).any() else "not sprayed"
        print(
            f"  [{i}] {m['label']} | Area: {m['mask_array'].sum()} px "
            f"| Predicted IoU: {m['predicted_iou']:.2f} | {on_map}"
        )

    # Pixels the model itself labelled as non-weed that still sit on the spray map
    # (masks can overlap). Uses the model's own labels, not ground truth.
    other_pixels = np.zeros((h, w), dtype=bool)
    for m in final_state["masks"]:
        if "weed" not in str(m["label"]).lower():
            other_pixels |= m["mask_array"]
    if other_pixels.any():
        overlap = int((other_pixels & sprayed).sum())
        print(
            f"• Non-weed-labelled pixels on spray map: {overlap} of {int(other_pixels.sum())} "
            f"({100.0 * overlap / other_pixels.sum():.1f}%)"
        )

    print(f"\n• Refinement Iterations    : {final_state['refinement_count']}")
    
    spray_info = final_state.get("spray_map", {})
    print(f"• Weed Infestation Area    : {spray_info.get('infestation_percentage', 0.0)}%")
    print(f"• Chemical Volume Saved    : {spray_info.get('chemical_savings_percentage', 0.0):.1f}% vs Broadcast")
    print(f"• Status                   : {spray_info.get('status', 'Complete')}")
    print("=" * 65 + "\n")

    # 5. Export visualization
    plot_and_save_results(img, final_state, output_path=args.output)


if __name__ == "__main__":
    main()
