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


def plot_and_save_results(
    image: Image.Image,
    state: dict,
    output_path: str = "output_spray_map.png"
) -> None:
    """Generates a 3-panel visualization: Original, Bounding Boxes, and Precision Spray Map."""
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

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Panel 1: Raw Field Photo
    axes[0].imshow(np_img)
    axes[0].set_title("1. Original Sensor Stream", fontsize=12, fontweight="bold")
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

    # Panel 3: SAM 2 Precision Spray Map
    overlay = np_img.copy()
    h, w = np_img.shape[:2]
    composite_mask = np.zeros((h, w), dtype=bool)

    for m in masks:
        mask_arr = m["mask_array"]
        composite_mask |= mask_arr
        # Paint weed foliage in red semi-transparent overlay
        overlay[mask_arr] = [220, 30, 30]

    # Blend original and mask overlay
    blended = (0.55 * np_img + 0.45 * overlay).astype(np.uint8)
    axes[2].imshow(blended)

    savings = spray_info.get("chemical_savings_percentage", 0.0)
    infest = spray_info.get("infestation_percentage", 0.0)
    axes[2].set_title(
        f"3. SAM 2 Spray Map\n[Weeds: {infest}% | SAVINGS: {savings:.1f}%]",
        fontsize=12, fontweight="bold", color="darkgreen"
    )
    axes[2].axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    logger.info("Saved 3-panel visualization to: %s", output_path)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Run AgriAgent Grounded-SAM 2 Pipeline")
    parser.add_argument("--image", type=str, default=None, help="Path to input image file")
    parser.add_argument("--prompt", type=str, default="cotton weed . broadleaf plant .", help="Detection prompt")
    parser.add_argument("--mock", action="store_true", help="Force mock mode even if GPU/PyTorch are available")
    parser.add_argument("--output", type=str, default="output_spray_map.png", help="Output visualization path")
    args = parser.parse_args()

    # 1. Load or synthesize test image
    if args.image and Path(args.image).exists():
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
    print("\n" + "=" * 65)
    print("🌾 AGRIAGENT SYSTEM-1 REFLEX RESULTS")
    print("=" * 65)
    print(f"• Candidate Bounding Boxes : {len(final_state['boxes'])}")
    for i, b in enumerate(final_state["boxes"], 1):
        print(f"  [{i}] {b['label']} (conf: {b['score']:.2f}) -> [{b['x1']:.1f}, {b['y1']:.1f}, {b['x2']:.1f}, {b['y2']:.1f}]")

    print(f"\n• Segmented Instance Masks : {len(final_state['masks'])}")
    for i, m in enumerate(final_state["masks"], 1):
        print(f"  [{i}] Area: {m['mask_array'].sum()} px | Predicted IoU: {m['predicted_iou']:.2f}")

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
