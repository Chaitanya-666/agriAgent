"""F1 experiment (verification report 23 Oct): plant rules v3 vs a size limit on rule 4,
DEVELOPMENT set only (eval_manifest_v2). The held-out manifest is not read.

The variant changes only rule 4 of src/vision/plant_candidates.py: an off-row patch in a photo
without crop masks is a weed only if it is smaller than LIMIT x the median on-row patch
(LIMIT = 0.25, 0.5, 1.0, 1.5); otherwise "unsure" (never sprayed). Detection and segmentation run once per photo; both rule
versions are applied to the same masks, in the product's own way (gate-approved zones + rule
weeds minus crop). Each photo is scored as taken and rotated 90 degrees (labels rotated).

Usage: python scripts/experiment_f1_row_rule.py   (real models, about 5 minutes)
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import src.vision.plant_candidates as pc  # noqa: E402
from src.evaluation.crop_protection import ground_truth_masks, spray_metrics, vegetation_mask  # noqa: E402
from src.evaluation.iou_dice import spray_footprint  # noqa: E402
from src.workflow import (
    VisionWorkflowRunner,
    create_initial_state,
    crop_pixels,
    crop_reference_masks,
)  # noqa: E402


def classify_variant_b(image_rgb, crop_masks, limit=0.25):
    """Copy of pc.classify_plants (v3) with rule 4 changed; everything else identical."""
    full_h, full_w = image_rgb.shape[:2]
    step = max(1, int(np.ceil(max(full_h, full_w) / pc.WORK_LONG_SIDE)))
    small = image_rgb[::step, ::step]
    vegetation = vegetation_mask(small)
    crop_ref = np.zeros(vegetation.shape, dtype=bool)
    crop_sizes = []
    for mask in crop_masks:
        m = np.asarray(mask, dtype=bool)[::step, ::step][
            : vegetation.shape[0], : vegetation.shape[1]
        ]
        crop_ref |= m
        size = int((m & vegetation).sum())
        if size:
            crop_sizes.append(size)
    median_crop = float(np.median(crop_sizes)) if crop_sizes else None
    rows = pc.row_profile(vegetation)
    labels, count = pc.connected_components(
        pc.close_gaps(vegetation, max(1, round(0.01 * max(vegetation.shape))))
    )
    labels = np.where(vegetation, labels, 0)
    found = []
    for index in range(1, count + 1):
        patch = labels == index
        area = int(patch.sum())
        if area < pc.MIN_PATCH_PX:
            continue
        overlap = float((patch & crop_ref).sum()) / area
        on_row = None
        if rows is not None:
            orientation, profile = rows
            ys, xs = np.nonzero(patch)
            centre = ys.mean() if orientation == "horizontal" else xs.mean()
            on_row = bool(profile[int(centre)] >= 0.5 * profile.max())
        found.append((patch, area, overlap, on_row))
    row_sizes = [a for _, a, ov, on in found if on and ov < pc.CROP_OVERLAP]
    median_row = float(np.median(row_sizes)) if row_sizes else None
    weed = np.zeros(vegetation.shape, dtype=bool)
    crop = np.zeros(vegetation.shape, dtype=bool)
    patches = []
    for patch, area, overlap, on_row in found:
        if overlap >= pc.CROP_OVERLAP:
            verdict = "crop"
        elif on_row:
            verdict = "crop"
        elif median_crop is not None:
            verdict = "weed" if area < pc.SMALL_VS_CROP * median_crop else "unsure"
        elif on_row is False:  # rule 4, changed: size against the plants on the row
            verdict = "weed" if median_row is not None and area < limit * median_row else "unsure"
        else:
            verdict = "unsure"
        if verdict == "weed":
            weed[patch] = True
        elif verdict == "crop":
            crop[patch] = True
        patches.append({"verdict": verdict})

    def full(mask):
        return np.repeat(np.repeat(mask, step, axis=0), step, axis=1)[:full_h, :full_w]

    return full(weed), full(crop), patches


def rotate_box(
    box, width
):  # PIL rotate(90, expand=True) is counter-clockwise: (x, y) -> (y, W - x)
    x1, y1, x2, y2 = box
    return [y1, width - x2, y2, width - x1]


def mostly_sprayed(crop_objects, sprayed):
    return sum(bool((p & sprayed).sum() >= 0.5 * p.sum()) for p in crop_objects if p.any())


runner = VisionWorkflowRunner(mock_mode=False, plant_rules=True)
runner.system2 = None
manifest = json.loads((ROOT / "data/manifests/eval_manifest_v2.json").read_text())
names = {"sugarbeet": "sugar beet", "cotton": "cotton"}
totals = {}
for item in manifest["items"]:
    base = Image.open(ROOT / item["image_path"]).convert("RGB")
    for view in ("as taken", "rotated 90"):
        image = base if view == "as taken" else base.rotate(90, expand=True)
        anns = (
            item["annotations"]
            if view == "as taken"
            else [{**a, "box": rotate_box(a["box"], base.size[0])} for a in item["annotations"]]
        )
        crop = names[item["crop_type"]]
        state = runner.run(create_initial_state(image, text_prompt=f"weed . {crop} plant ."))
        rgb = np.asarray(image)
        h, w = rgb.shape[:2]
        masks, prompt = state.get("masks", []), state.get("text_prompt")
        zones = state["artifacts"]["spray_map"].payload.get("approved_spray_zones", [])
        other = np.zeros((h, w), dtype=bool)
        for z in zones:
            if z.get("approved_by") != "plant_rules":
                other |= np.asarray(z["mask"], dtype=bool)
        refs, crop_px_det = (
            crop_reference_masks(masks, prompt, (h, w)),
            crop_pixels(masks, prompt, (h, w)),
        )
        cp, wp, co, wo = ground_truth_masks(anns, vegetation_mask(rgb))
        for rule, fn in (("v3", pc.classify_plants),) + tuple(
            (f"x{t}", (lambda t: lambda a, b: classify_variant_b(a, b, t))(t))
            for t in (0.25, 0.5, 1.0, 1.5)
        ):
            weed, crop_rule, patches = fn(rgb, refs)
            raw = other | (weed & ~crop_rule & ~crop_px_det)
            sprayed = spray_footprint(raw, 10)
            m = spray_metrics(sprayed, cp, wp, co, wo)
            key = (item["crop_type"], view, rule)
            t = totals.setdefault(
                key,
                {
                    "crop_hit": 0,
                    "crop": 0,
                    "weed_hit": 0,
                    "weed": 0,
                    "plants": 0,
                    "touched": 0,
                    "mostly": 0,
                    "weeds": 0,
                    "weeds_hit": 0,
                    "unsure": 0,
                    "imgs": 0,
                },
            )
            t["crop_hit"] += m["crop_pixels_sprayed"]
            t["crop"] += m["crop_pixels"]
            t["weed_hit"] += m["weed_pixels_sprayed"]
            t["weed"] += m["weed_pixels"]
            t["plants"] += m.get("crop_plants", 0)
            t["touched"] += m.get("crop_plants_damaged", 0)
            t["mostly"] += mostly_sprayed(co, sprayed)
            t["weeds"] += m.get("weed_plants", 0)
            t["weeds_hit"] += m.get("weed_plants_hit", 0)
            t["unsure"] += sum(p["verdict"] == "unsure" for p in patches)
            t["imgs"] += 1
    print("done", item["image_id"], flush=True)

print("\nRESULTS (development set only)")
print(
    f"{'crop':9s} {'view':11s} {'rule':4s} {'crop px sprayed':>16s} {'weed recall':>12s} {'beets touched':>14s} {'beets >=50%':>12s} {'weeds hit':>10s} {'unsure':>7s}"
)


def pct(a, b):
    return f"{100 * a / b:.2f}%" if b else "-"


for (ct, view, rule), t in sorted(totals.items()):
    print(
        f"{ct:9s} {view:11s} {rule:4s} {pct(t['crop_hit'], t['crop']):>16s} {pct(t['weed_hit'], t['weed']):>12s} "
        f"{t['touched']:>6d}/{t['plants']:<7d} {t['mostly']:>5d}/{t['plants']:<6d} {t['weeds_hit']:>4d}/{t['weeds']:<5d} {t['unsure']:>7d}"
    )
