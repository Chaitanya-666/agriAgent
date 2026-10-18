"""T2.2: ask several back-ends "crop or weed?" on labelled patches and count who is right.

Patches are cut from data/manifests/eval_manifest_v2.json (official labels), so the true answer
is known. Each patch is also saved as a PNG so a person can look at it.

Back-ends:
    groq        Groq qwen/qwen3.8-27b through HostedGroqProvider, told which crop the field grows
    clef        Cloudflare Workers AI @cf/cloudflare/clef-flash, a "choice" question with the image
    row_rule    no model: crops grow in rows, so a plant whose centre lies on the densest
                vegetation band of the whole image is called crop; abstains without clear rows

Usage:
    python scripts/compare_crop_or_weed.py                  # 20 patches, writes data/outputs/t2_2/
    python scripts/compare_crop_or_weed.py --row-rule-only  # recompute the row rule only
"""

import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from src.agents.evidence import ClefEvidence, GroqEvidence, RowRuleEvidence, cut_patch  # noqa: E402

MANIFEST = PROJECT_ROOT / "data/manifests/eval_manifest_v2.json"
OUT_DIR = PROJECT_ROOT / "data/outputs/t2_2"
CROP_NAMES = {"sugarbeet": "sugar beet", "cotton": "cotton"}
PATCH_PLAN = [("sugarbeet", "crop", 10), ("sugarbeet", "weed", 6), ("cotton", "weed", 4)]
MIN_SIDE_PX = 24  # smaller plants are a few pixels wide; nobody can judge them from a patch


def pick_patches(seed: int = 0) -> List[Dict[str, Any]]:
    items = json.loads(MANIFEST.read_text())["items"]
    rng = random.Random(seed)
    patches = []
    for crop_type, category, count in PATCH_PLAN:
        pool = []
        for item in items:
            if item["crop_type"] != crop_type:
                continue
            for ann in item["annotations"]:
                x1, y1, x2, y2 = ann["box"]
                too_small = min(x2 - x1, y2 - y1) < MIN_SIDE_PX
                whole_image = (x2 - x1) * (y2 - y1) > 0.5 * item["width"] * item["height"]
                if ann["category"] == category and not too_small and not whole_image:
                    pool.append((item, ann))
        for item, ann in rng.sample(pool, count):
            patches.append({"item": item, "ann": ann, "truth": category})
    return patches


def rerun_row_rule() -> None:
    """Recompute only the row rule on the saved results (no model calls)."""
    items = {i["image_id"]: i for i in json.loads(MANIFEST.read_text())["items"]}
    results = json.loads((OUT_DIR / "results.json").read_text())
    by_patch = {
        f"{n:02d}_{p['item']['crop_type']}_{p['truth']}": p for n, p in enumerate(pick_patches())
    }
    for row in results:
        item = items[row["image"]]
        image = Image.open(PROJECT_ROOT / item["image_path"])
        crop = CROP_NAMES[item["crop_type"]]
        evidence = RowRuleEvidence()(image, by_patch[row["patch"]]["ann"]["box"], crop)
        row["row_rule"], row["row_rule_raw"] = evidence.verdict, evidence.detail
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2))
    summarise(results)


def summarise(results: List[Dict[str, Any]]) -> None:
    print("\nback-end   correct / answered   abstained   mean seconds")
    for name in ("groq", "clef", "row_rule"):
        answered = [r for r in results if r[name] is not None]
        correct = sum(r[name] == r["truth"] for r in answered)
        print(
            f"{name:9s}  {correct:3d} / {len(answered):<3d}           {len(results) - len(answered):3d}"
            f"         {np.mean([r[f'{name}_s'] for r in results]):.2f}"
        )


def main() -> int:
    if "--row-rule-only" in sys.argv:
        rerun_row_rule()
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = {"groq": GroqEvidence(), "clef": ClefEvidence(), "row_rule": RowRuleEvidence()}
    results = []
    for index, p in enumerate(pick_patches()):
        item, ann, truth = p["item"], p["ann"], p["truth"]
        crop = CROP_NAMES[item["crop_type"]]
        image = Image.open(PROJECT_ROOT / item["image_path"])
        patch = cut_patch(image, ann["box"])
        patch_id = f"{index:02d}_{item['crop_type']}_{truth}"
        patch.save(OUT_DIR / f"{patch_id}.png")

        row = {"patch": patch_id, "image": item["image_id"], "truth": truth, "label": ann["label"]}
        for name, source in sources.items():
            start = time.time()
            evidence = source(image, ann["box"], crop)
            row[name] = evidence.verdict
            row[f"{name}_raw"] = evidence.detail
            row[f"{name}_s"] = round(time.time() - start, 2)
        results.append(row)
        print(
            f"{patch_id:24s} truth={truth:4s}  groq={row['groq']}  clef={row['clef']}  "
            f"row_rule={row['row_rule']}",
            flush=True,
        )

    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2))
    summarise(results)
    print(f"\nPatches and results.json in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
