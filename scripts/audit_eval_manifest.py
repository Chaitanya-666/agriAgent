"""Audit data/manifests/eval_manifest_v1.json against the official dataset labels (task T3.1).

For each manifest image this draws our annotations next to the official ones and writes a
summary table, so a person can mark every image trusted / fix / drop by eye.

Official labels expected on disk (small targeted downloads, see data/datasets/):
    data/datasets/sugarbeets_weeds_official/data/{train,val}/{image,annotation}/   (Kaggle wangyongkun/sugarbeetsandweeds)
    data/datasets/cottonweeddet3_official/{images,annotations}/                   (Kaggle yuzhenlu/cottonweeddet3)

Usage:
    python scripts/audit_eval_manifest.py            # writes data/outputs/audit/
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = PROJECT_ROOT / "data/manifests/eval_manifest_v1.json"
BEET_DIR = PROJECT_ROOT / "data/datasets/sugarbeets_weeds_official/data"
COTTON_DIR = PROJECT_ROOT / "data/datasets/cottonweeddet3_official"
OUT_DIR = PROJECT_ROOT / "data/outputs/audit"

# (category, x1, y1, x2, y2) in the pixel frame of the image it belongs to
LabelBox = Tuple[str, float, float, float, float]


def official_beet(name: str) -> Tuple[Optional[Path], List[LabelBox]]:
    for split in ("train", "val"):
        xml_path = BEET_DIR / split / "annotation" / f"{name}.xml"
        if xml_path.exists():
            boxes: List[LabelBox] = []
            for obj in ET.parse(xml_path).getroot().iter("object"):
                bb = obj.find("bndbox")
                assert bb is not None
                category = "crop" if obj.findtext("name") == "sugarbeet" else "weed"
                coords = [float(bb.findtext(k) or 0) for k in ("xmin", "ymin", "xmax", "ymax")]
                boxes.append((category, *coords))
            return BEET_DIR / split / "image" / f"{name}.png", boxes
    return None, []


def official_cotton(name: str) -> Tuple[Optional[Path], List[LabelBox]]:
    json_path = COTTON_DIR / "annotations" / f"{name}.json"
    if not json_path.exists():
        return None, []
    record = next(iter(json.loads(json_path.read_text()).values()))
    boxes: List[LabelBox] = []
    for region in record["regions"]:
        s = region["shape_attributes"]
        # CottonWeedDet3 labels weed species only; no cotton plant is annotated.
        boxes.append(("weed", s["x"], s["y"], s["x"] + s["width"], s["y"] + s["height"]))
    return COTTON_DIR / "images" / f"{name}.jpg", boxes


def iou(a: LabelBox, b: LabelBox) -> float:
    ix = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    iy = max(0.0, min(a[4], b[4]) - max(a[2], b[2]))
    inter = ix * iy
    union = (a[3] - a[1]) * (a[4] - a[2]) + (b[3] - b[1]) * (b[4] - b[2]) - inter
    return inter / union if union > 0 else 0.0


def match(ours: List[LabelBox], official: List[LabelBox]) -> Tuple[int, float]:
    """Greedy same-category matching at IoU >= 0.5; returns (matched count, mean IoU)."""
    used: set = set()
    ious = []
    for o in ours:
        best, best_j = 0.0, None
        for j, t in enumerate(official):
            if j not in used and t[0] == o[0] and iou(o, t) > best:
                best, best_j = iou(o, t), j
        if best_j is not None and best >= 0.5:
            used.add(best_j)
            ious.append(best)
    return len(ious), float(np.mean(ious)) if ious else 0.0


def image_similarity(fixture: Image.Image, official: Image.Image) -> float:
    """Mean absolute pixel difference (0-255) after resizing the official image to the fixture."""
    a = np.asarray(fixture.convert("RGB"), dtype=float)
    b = np.asarray(official.convert("RGB").resize(fixture.size), dtype=float)
    return float(np.abs(a - b).mean())


def draw(ax, image: Image.Image, boxes: List[LabelBox], title: str) -> None:
    import matplotlib.patches as patches

    ax.imshow(image)
    for category, x1, y1, x2, y2 in boxes:
        colour = "lime" if category == "crop" else "red"
        ax.add_patch(
            patches.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, edgecolor=colour, linewidth=2)
        )
    ax.set_title(title, fontsize=10)
    ax.axis("off")


def main() -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    items = json.loads(MANIFEST.read_text())["items"]
    rows = []
    for item in items:
        image_id = item["image_id"]
        crop_type = item["crop_type"]
        name = image_id.split("_", 1)[1].rsplit(".", 1)[0]
        fixture = Image.open(PROJECT_ROOT / item["image_path"])
        ours: List[LabelBox] = [
            (a["category"], *map(float, a["box"])) for a in item["annotations"]
        ]

        if crop_type == "sugarbeet":
            official_path, official = official_beet(name)
        else:
            official_path, official = official_cotton(name)
        if official_path is None:
            print(f"{image_id}: no official label found", file=sys.stderr)
            continue
        official_img = Image.open(official_path)

        # Bring our boxes into the official image's pixel frame before comparing.
        sx = official_img.width / fixture.width
        sy = official_img.height / fixture.height
        ours_scaled = [(c, x1 * sx, y1 * sy, x2 * sx, y2 * sy) for c, x1, y1, x2, y2 in ours]
        matched, mean_iou = match(ours_scaled, official)

        def counts(boxes: List[LabelBox]) -> Dict[str, int]:
            return {k: sum(1 for b in boxes if b[0] == k) for k in ("crop", "weed")}

        row = {
            "image": image_id,
            "fixture_size": f"{fixture.width}x{fixture.height}",
            "official_size": f"{official_img.width}x{official_img.height}",
            "aspect_kept": abs(fixture.width / fixture.height - official_img.width / official_img.height) < 0.01,
            "pixel_diff": round(image_similarity(fixture, official_img), 1),
            "ours": counts(ours),
            "official": counts(official),
            "matched": matched,
            "mean_iou": round(mean_iou, 2),
        }
        rows.append(row)

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        draw(axes[0], fixture, ours, f"OURS (manifest v1)  crop={row['ours']['crop']} weed={row['ours']['weed']}")
        draw(
            axes[1],
            official_img,
            official,
            f"OFFICIAL  crop={row['official']['crop']} weed={row['official']['weed']}",
        )
        fig.suptitle(
            f"{image_id}   matched {matched}/{len(ours)} of our boxes (IoU>=0.5)   "
            f"green = crop, red = weed",
            fontsize=11,
        )
        plt.tight_layout()
        plt.savefig(OUT_DIR / f"{Path(image_id).stem}.png", dpi=90)
        plt.close(fig)

    (OUT_DIR / "audit_table.json").write_text(json.dumps(rows, indent=2))
    print(f"{'image':38s} {'fixture':>9s} {'official':>9s} aspect diff  ours(c/w) official(c/w) matched")
    for r in rows:
        print(
            f"{r['image']:38s} {r['fixture_size']:>9s} {r['official_size']:>9s} "
            f"{'ok ' if r['aspect_kept'] else 'BAD'}  {r['pixel_diff']:5.1f}  "
            f"{r['ours']['crop']}/{r['ours']['weed']:<6d}  {r['official']['crop']}/{r['official']['weed']:<11d} "
            f"{r['matched']}/{r['ours']['crop'] + r['ours']['weed']} (IoU {r['mean_iou']})"
        )
    print(f"\nFigures and audit_table.json written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
