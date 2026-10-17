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

import base64
import io
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from src.agronomy.provider_contract import LLMRequest  # noqa: E402
from src.agronomy.providers.hosted_groq import HostedGroqProvider  # noqa: E402

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


def cut_patch(image: Image.Image, box: List[float]) -> Image.Image:
    """Box plus a 15% margin, at least 64 px, scaled so the long side is 384 px."""
    x1, y1, x2, y2 = box
    mx, my = max(0.15 * (x2 - x1), (64 - (x2 - x1)) / 2), max(0.15 * (y2 - y1), (64 - (y2 - y1)) / 2)
    crop = image.crop(
        (max(0, x1 - mx), max(0, y1 - my), min(image.width, x2 + mx), min(image.height, y2 + my))
    )
    scale = 384 / max(crop.size)
    return crop.resize((round(crop.width * scale), round(crop.height * scale)))


def data_url(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def ask_groq(provider: HostedGroqProvider, patch: Image.Image, crop: str) -> Tuple[Optional[str], str]:
    prompt = (
        f"This close-up is cut from a photo of a {crop} field. Is the plant in the centre of the "
        f"image the crop ({crop}) or a weed? Reply ONLY with JSON: "
        '{"answer": "crop" or "weed", "confidence": number between 0 and 1}'
    )
    for attempt in range(6):
        resp = provider.generate(LLMRequest(user_prompt=prompt, image=patch, timeout_seconds=60))
        if resp.error and "429" in resp.error:
            time.sleep(15 * (attempt + 1))  # free tier: about 8,000 tokens per minute
            continue
        if resp.error:
            return None, resp.error
        answer = str((resp.parsed_json or {}).get("answer", "")).lower()
        return (answer if answer in ("crop", "weed") else None), resp.text_content
    return None, "rate limited"


def ask_clef(patch: Image.Image, crop: str) -> Tuple[Optional[str], str]:
    account, token = os.getenv("CLOUDFLARE_ACCOUNT_ID"), os.getenv("CLOUDFLARE_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/clef-flash"
    body = {
        "model": "clef-flash",
        "state": f"A close-up cut from a photo of a {crop} field.",
        "images": [data_url(patch)],
        "questions": {
            "plant": {
                "type": "choice",
                "instructions": f"Is the plant in the centre of the image the crop ({crop}) or a weed?",
                "criteria": {"crop": f"a {crop} plant", "weed": f"any plant that is not {crop}"},
            }
        },
    }
    resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=body, timeout=60)
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    answer = resp.json().get("result", {}).get("answers", {}).get("plant", {})
    choice = answer.get("choice") or answer.get("value")
    return (choice if choice in ("crop", "weed") else None), json.dumps(answer)


def otsu_threshold(values: np.ndarray) -> float:
    """Threshold that best separates the values into two groups (Otsu's method)."""
    hist, edges = np.histogram(values, bins=256)
    centres = (edges[:-1] + edges[1:]) / 2
    weight = np.cumsum(hist)
    mean = np.cumsum(hist * centres)
    total_weight, total_mean = weight[-1], mean[-1]
    between = (total_mean * weight - mean * total_weight) ** 2 / (
        weight * (total_weight - weight) + 1e-9
    )
    return float(centres[np.argmax(between[:-1])])


def row_rule(image: Image.Image, box: List[float]) -> Tuple[Optional[str], str]:
    rgb = np.asarray(image.convert("RGB"), dtype=float)
    excess_green = 2 * rgb[..., 1] - rgb[..., 0] - rgb[..., 2]
    # Soil colour differs between fields, so a fixed cutoff fails; Otsu picks one per image.
    vegetation = excess_green > otsu_threshold(excess_green)
    best = None
    for axis, name in ((1, "horizontal"), (0, "vertical")):
        profile = np.convolve(vegetation.sum(axis=axis), np.ones(15) / 15, mode="same")
        peakiness = profile.max() / (profile.mean() + 1e-6)
        if best is None or peakiness > best[0]:
            best = (peakiness, name, profile)
    assert best is not None
    peakiness, orientation, profile = best
    if peakiness < 2.0:
        return None, f"no clear rows (peakiness {peakiness:.1f})"
    centre = (box[1] + box[3]) / 2 if orientation == "horizontal" else (box[0] + box[2]) / 2
    on_row = profile[int(min(centre, len(profile) - 1))] >= 0.5 * profile.max()
    return ("crop" if on_row else "weed"), f"{orientation} rows, peakiness {peakiness:.1f}"


def rerun_row_rule() -> None:
    """Recompute only the row rule on the saved results (no model calls)."""
    items = {i["image_id"]: i for i in json.loads(MANIFEST.read_text())["items"]}
    results = json.loads((OUT_DIR / "results.json").read_text())
    by_patch = {f"{n:02d}_{p['item']['crop_type']}_{p['truth']}": p for n, p in enumerate(pick_patches())}
    for row in results:
        item = items[row["image"]]
        image = Image.open(PROJECT_ROOT / item["image_path"])
        row["row_rule"], row["row_rule_raw"] = row_rule(image, by_patch[row["patch"]]["ann"]["box"])
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
    groq = HostedGroqProvider()
    results = []
    for index, p in enumerate(pick_patches()):
        item, ann, truth = p["item"], p["ann"], p["truth"]
        crop = CROP_NAMES[item["crop_type"]]
        image = Image.open(PROJECT_ROOT / item["image_path"])
        patch = cut_patch(image, ann["box"])
        patch_id = f"{index:02d}_{item['crop_type']}_{truth}"
        patch.save(OUT_DIR / f"{patch_id}.png")

        row = {"patch": patch_id, "image": item["image_id"], "truth": truth, "label": ann["label"]}
        for name, ask in (
            ("groq", lambda: ask_groq(groq, patch, crop)),
            ("clef", lambda: ask_clef(patch, crop)),
            ("row_rule", lambda: row_rule(image, ann["box"])),
        ):
            start = time.time()
            answer, raw = ask()
            row[name] = answer
            row[f"{name}_raw"] = raw
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
