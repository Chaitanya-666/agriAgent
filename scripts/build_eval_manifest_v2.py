"""Build data/manifests/eval_manifest_v2.json from official dataset labels only.

eval_manifest_v1 failed the T3.1 audit (scripts/audit_eval_manifest.py): its boxes match
almost none of the official labels. v2 copies boxes straight from the official files.

Sources (Kaggle, small targeted downloads; needs a Kaggle token, see README):
    wangyongkun/sugarbeetsandweeds  whole dataset, 67 MB, 512x512, labels: sugarbeet + weed
    yuzhenlu/cottonweeddet3         8 photos + their annotation files only, labels: weed species

Selection rule (fixed, so nobody hand-picks easy images):
    sugar beet: of the images that contain at least one crop AND one weed box, sorted in
                natural order, take 30 evenly spaced (np.linspace over the list).
    cotton:     the 8 unique photos matching our old fixtures; CM_29 and CM_40 are byte-identical
                copies of CM_11 and CM_36 in the official dataset itself, so they are left out.

Usage:
    python scripts/build_eval_manifest_v2.py           # downloads what is missing, writes the manifest
"""

import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BEET_DATASET = "wangyongkun/sugarbeetsandweeds"
COTTON_DATASET = "yuzhenlu/cottonweeddet3"
BEET_DIR = PROJECT_ROOT / "data/datasets/sugarbeets_weeds_official"
COTTON_DIR = PROJECT_ROOT / "data/datasets/cottonweeddet3_official"
OUTPUT = PROJECT_ROOT / "data/manifests/eval_manifest_v2.json"

NUM_BEET = 30
COTTON_NAMES = [f"20190613_6062W_CM_{n}" for n in (11, 17, 21, 30, 33, 36, 37, 39)]


def kaggle(*args: str) -> None:
    exe = shutil.which("kaggle") or str(Path(sys.executable).with_name("kaggle"))
    subprocess.run([exe, *args], check=True, stdout=subprocess.DEVNULL)


def fetch_file(dataset: str, remote: str, target_dir: Path) -> Path:
    """Download one file from a Kaggle dataset; single files may arrive zipped."""
    target = target_dir / Path(remote).name
    if target.exists():
        return target
    target_dir.mkdir(parents=True, exist_ok=True)
    kaggle("datasets", "download", dataset, "-f", remote, "-p", str(target_dir), "-q")
    zipped = target.with_name(target.name + ".zip")
    if zipped.exists():
        with zipfile.ZipFile(zipped) as zf:
            zf.extractall(target_dir)
        zipped.unlink()
    return target


def natural_key(name: str) -> List[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def beet_items() -> List[Dict[str, Any]]:
    if not (BEET_DIR / "data").exists():
        BEET_DIR.mkdir(parents=True, exist_ok=True)
        kaggle("datasets", "download", BEET_DATASET, "-p", str(BEET_DIR), "--unzip", "-q")

    candidates = []
    for xml_path in BEET_DIR.glob("data/*/annotation/*.xml"):
        root = ET.parse(xml_path).getroot()
        names = [obj.findtext("name") for obj in root.iter("object")]
        if "sugarbeet" in names and "weed" in names:
            candidates.append(xml_path)
    candidates.sort(key=lambda p: natural_key(p.stem))
    picks = [candidates[i] for i in np.linspace(0, len(candidates) - 1, NUM_BEET).round().astype(int)]

    items = []
    for xml_path in picks:
        root = ET.parse(xml_path).getroot()
        image_path = xml_path.parent.parent / "image" / f"{xml_path.stem}.png"
        annotations = []
        for obj in root.iter("object"):
            bb = obj.find("bndbox")
            assert bb is not None
            x1, y1, x2, y2 = (float(bb.findtext(k) or 0) for k in ("xmin", "ymin", "xmax", "ymax"))
            label = obj.findtext("name") or ""
            annotations.append(
                {
                    "category": "crop" if label == "sugarbeet" else "weed",
                    "label": label,
                    "box": [x1, y1, x2, y2],
                    "area": (x2 - x1) * (y2 - y1),
                }
            )
        items.append(
            make_item(f"beet_{xml_path.stem}.png", "sugarbeet", image_path, annotations,
                      f"{BEET_DATASET}: {xml_path.relative_to(BEET_DIR)}")
        )
    return items


def cotton_items() -> List[Dict[str, Any]]:
    items = []
    for name in COTTON_NAMES:
        ann_path = fetch_file(COTTON_DATASET, f"CottonWeedDet3/annotations/{name}.json", COTTON_DIR / "annotations")
        image_path = fetch_file(COTTON_DATASET, f"CottonWeedDet3/images/{name}.jpg", COTTON_DIR / "images")
        record = next(iter(json.loads(ann_path.read_text()).values()))
        annotations = []
        for region in record["regions"]:
            s = region["shape_attributes"]
            annotations.append(
                {
                    "category": "weed",
                    "label": region["region_attributes"]["class"],
                    "box": [s["x"], s["y"], s["x"] + s["width"], s["y"] + s["height"]],
                    "area": s["width"] * s["height"],
                }
            )
        items.append(
            make_item(f"cotton_{name}.jpg", "cotton", image_path, annotations,
                      f"{COTTON_DATASET}: CottonWeedDet3/annotations/{name}.json")
        )
    return items


def make_item(image_id: str, crop_type: str, image_path: Path, annotations: List[Dict[str, Any]],
              source: str) -> Dict[str, Any]:
    width, height = Image.open(image_path).size
    for index, ann in enumerate(annotations):
        ann["id"] = f"{Path(image_id).stem}_{index:02d}"
        ann["box"] = [round(v, 2) for v in ann["box"]]
        ann["area"] = round(ann["area"], 1)
    return {
        "image_id": image_id,
        "image_path": str(image_path.relative_to(PROJECT_ROOT)),
        "crop_type": crop_type,
        "width": width,
        "height": height,
        "split": "test",
        "has_crop_labels": crop_type == "sugarbeet",
        "num_annotations": len(annotations),
        "source": source,
        "annotations": annotations,
    }


def main() -> int:
    items = beet_items() + cotton_items()
    manifest = {
        "manifest_version": "2.0.0",
        "dataset_name": "AgriAgent evaluation set v2 (official labels only)",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": (
            "Built by scripts/build_eval_manifest_v2.py. Boxes are copied unchanged from the "
            "official annotation files; nothing is hand-drawn. Sugar beet images carry crop and "
            "weed boxes; cotton images carry weed boxes only (CottonWeedDet3 does not label "
            "cotton), so cotton images are excluded from crop-protection metrics. Labels are "
            "boxes, not pixel masks. Replaces eval_manifest_v1, which failed the T3.1 audit."
        ),
        "license": "Academic use; see each Kaggle dataset page",
        "selection_rule": __doc__.split("Selection rule")[1].split("Usage:")[0].strip(" :\n"),
        "split_summary": {
            "sugarbeet": sum(1 for i in items if i["crop_type"] == "sugarbeet"),
            "cotton": sum(1 for i in items if i["crop_type"] == "cotton"),
            "total_images": len(items),
        },
        "items": items,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n")
    crop_boxes = sum(a["category"] == "crop" for i in items for a in i["annotations"])
    weed_boxes = sum(a["category"] == "weed" for i in items for a in i["annotations"])
    print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT)}: {len(items)} images, "
          f"{crop_boxes} crop boxes, {weed_boxes} weed boxes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
