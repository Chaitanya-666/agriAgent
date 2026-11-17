"""
Five-step walkthrough figure for the FYP deck (slide 17): one photo through the real pipeline.

    python scripts/make_walkthrough_figure.py \
        --image data/outputs/test_photos/beet_X2-30-0.png --crop "sugar beet" \
        --output docs/slides/fyp_assets/walkthrough.png

Panels: 1 photo, 2 Grounding DINO boxes, 3 SAM 2 masks, 4 plant verdicts (the app's
"every plant" view), 5 the spray map the safety gate approved. Real models only: the
script stops if either model runs in mock mode. Prints the numbers shown in the panels.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.components.ui import plant_verdict_image  # noqa: E402
from scripts.run_live_pipeline import approved_spray_mask  # noqa: E402
from src.vision.visualization import draw_boxes, outline_masks  # noqa: E402
from src.workflow import VisionWorkflowRunner, create_initial_state  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--crop", default="sugar beet")
    ap.add_argument("--output", default="docs/slides/fyp_assets/walkthrough.png")
    args = ap.parse_args()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    img = Image.open(args.image).convert("RGB")
    runner = VisionWorkflowRunner(mock_mode=False, iou_threshold=0.85, plant_rules=True)
    if runner.detector.mock_mode or runner.segmenter.mock_mode:
        sys.exit("A model fell back to MOCK mode; refusing to draw a walkthrough from fake output.")
    state = create_initial_state(img)
    state["field_metadata"] = {"crop": args.crop}
    state = runner.run(state)
    if state.get("error"):
        sys.exit(f"Pipeline stopped: {state['error']}")

    w, h = img.size
    boxes, masks = state["boxes"], state["masks"]
    sprayed = approved_spray_mask(state, h, w)

    # Panel 3: SAM 2 masks, coloured by the detector's label (red: names a weed, blue: other).
    arr = np.asarray(img, dtype=float)
    over = arr.copy()
    for m in masks:
        colour = (220, 30, 30) if "weed" in str(m.get("label", "")).lower() else (30, 90, 220)
        over[m["mask_array"]] = colour
    seg = Image.fromarray((0.5 * arr + 0.5 * over).astype(np.uint8))

    verdicts, counts = plant_verdict_image(img, state)
    tint = arr.copy()
    tint[sprayed] = 0.4 * tint[sprayed] + 0.6 * np.array((220, 40, 40))
    spray_img = outline_masks(Image.fromarray(tint.astype(np.uint8)), [sprayed], color=(255, 0, 255))

    total = max(1, sum(counts.values()))
    spray_pct = 100.0 * sprayed.sum() / (w * h)
    titles = [
        "1  Photo + crop name",
        f"2  Grounding DINO: {len(boxes)} box{'es' if len(boxes) != 1 else ''}",
        f"3  SAM 2: {len(masks)} mask{'s' if len(masks) != 1 else ''}",
        "4  Plant rules: every patch",
        "5  Safety gate: spray map",
    ]
    subs = [
        f'prompt "weed . {args.crop} plant ."',
        "label + confidence per box",
        "red = labelled weed, blue = other",
        f"red {100 * counts['sprayed'] / total:.0f}% · green crop {100 * counts['crop'] / total:.0f}% · yellow unsure {100 * counts['unsure'] / total:.0f}%",
        f"{spray_pct:.1f}% of photo sprayed · {100 - spray_pct:.1f}% saved",
    ]
    panels = [img, draw_boxes(img, boxes), seg, verdicts, spray_img]

    fig, axes = plt.subplots(1, 5, figsize=(25, 6.2))
    for ax, p, t, s in zip(axes, panels, titles, subs):
        ax.imshow(p)
        ax.set_title(t + "\n", fontsize=17, fontweight="bold", loc="left")
        ax.text(0, -0.035, s, transform=ax.transAxes, fontsize=13, va="top")
        ax.axis("off")
    plt.tight_layout(w_pad=1.2)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=110, bbox_inches="tight", facecolor="white")
    print(f"saved {out}")
    print("boxes:", [(b["label"], round(b["score"], 2)) for b in boxes])
    print("masks:", len(masks), "| verdict pixel counts:", counts)
    print(f"sprayed {spray_pct:.2f}% of the photo")

    # Score against the official labels when the photo is in an evaluation manifest.
    import json

    from src.evaluation.crop_protection import ground_truth_masks, spray_metrics, vegetation_mask

    name = Path(args.image).name
    for manifest in ("eval_manifest_v2.json", "eval_manifest_v2_holdout.json"):
        path = PROJECT_ROOT / "data" / "manifests" / manifest
        if not path.exists():
            continue
        entries = json.loads(path.read_text()).get("items", [])
        entry = next((e for e in entries if e["image_id"] == name or Path(e["image_path"]).name == name.split("_", 1)[-1]), None)
        if entry:
            veg = vegetation_mask(np.asarray(img))
            crop_px, weed_px, crop_objs, weed_objs = ground_truth_masks(entry["annotations"], veg)
            print(f"official labels ({manifest}):", spray_metrics(sprayed, crop_px, weed_px, crop_objs, weed_objs))
            break


if __name__ == "__main__":
    main()
