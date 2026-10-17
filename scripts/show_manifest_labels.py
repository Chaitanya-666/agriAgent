"""Draw the boxes of an evaluation manifest on its images, one PNG per image.

Used for checking labels by eye (task V1): green = crop, red = weed.

Usage:
    python scripts/show_manifest_labels.py                                  # manifest v2
    python scripts/show_manifest_labels.py data/manifests/eval_manifest_v2.json
Output: data/outputs/manifest_labels/<image_id>.png
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "data/manifests/eval_manifest_v2.json"
OUT_DIR = PROJECT_ROOT / "data/outputs/manifest_labels"


def main() -> int:
    manifest = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MANIFEST
    items = json.loads(manifest.read_text())["items"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for item in items:
        image = Image.open(PROJECT_ROOT / item["image_path"]).convert("RGB")
        width = max(2, round(max(image.size) / 300))
        draw = ImageDraw.Draw(image)
        for ann in item["annotations"]:
            colour = (0, 220, 0) if ann["category"] == "crop" else (230, 0, 0)
            draw.rectangle(ann["box"], outline=colour, width=width)
        image.thumbnail((1024, 1024))
        image.save(OUT_DIR / f"{Path(item['image_id']).stem}.png")
    print(f"{len(items)} images written to {OUT_DIR.relative_to(PROJECT_ROOT)} (green = crop, red = weed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
