"""Run the automatable cases of test cycle 1 (Team Tasks, Part C) against the current code.

Screen checks drive the real app/app.py headlessly with Streamlit's AppTest. Cases that need an
uploaded photo call run_pipeline_on_image, the function the app runs after decoding an upload
(AppTest cannot upload files). Plant-level checks compare the approved spray zones with the
official labels of the photo in eval_manifest_v2 / eval_manifest_v2_holdout.

Usage:
    python scripts/verify_test_cycle1.py            # mock-mode cases (seconds, no GPU, no network)
    python scripts/verify_test_cycle1.py --real     # also the real-mode cases (GPU, cloud reasoning, minutes)

Each case prints PASS / FAIL / INFO (INFO: a measurement with no fixed expected value) and one
line of detail. The exit code is the number of failures.
"""

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

from app.app import run_pipeline_on_image  # noqa: E402
from app.components.pipeline import (  # noqa: E402
    ImageDecodeError,
    build_spray_geojson,
    create_sample_field_image,
    decode_uploaded_image,
)
from src.evaluation.crop_protection import (  # noqa: E402
    ground_truth_masks,
    spray_metrics,
    vegetation_mask,
)
from src.evaluation.iou_dice import spray_footprint  # noqa: E402

try:  # provider keys, as `streamlit run` loads them; otherwise only AppTest runs would have them
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

APP = str(PROJECT_ROOT / "app/app.py")
BEET = "data/datasets/sugarbeets_weeds_official/data/train/image"
COTTON = "data/datasets/cottonweeddet3_official/images"
PHOTOS = {
    "beet_X-10-0": (f"{BEET}/X-10-0.png", "Sugar Beet"),
    "beet_X2-30-0": (f"{BEET}/X2-30-0.png", "Sugar Beet"),
    "beet_X3-430-0": (f"{BEET}/X3-430-0.png", "Sugar Beet"),
    "beet_X3-130-0": (f"{BEET}/X3-130-0.png", "Sugar Beet"),
    "cotton_CM_17": (f"{COTTON}/20190613_6062W_CM_17.jpg", "Cotton"),
    "cotton_CM_11": (f"{COTTON}/20190613_6062W_CM_11.jpg", "Cotton"),
}
# Pause before cases that call the reasoning model. Groq's free tier allowed about 8,000 tokens per
# minute; since 30 Oct the default is Cloudflare (daily allowance), so a short pause is enough.
GROQ_PAUSE_S = 30 if os.getenv("REASONING_PROVIDER", "cloudflare").lower() == "groq" else 2

Result = Tuple[str, str]  # (PASS | FAIL | INFO, detail)


def run_app(prompt=None, threshold=None, force_system2=False, crop="Cotton", mock=True) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=900)
    at.run()
    at.sidebar.checkbox[0].set_value(mock)
    at.sidebar.selectbox[0].set_value(crop)
    at.run()
    if prompt is not None:
        at.sidebar.text_input[0].set_value(prompt)
    if threshold is not None:
        at.sidebar.slider[0].set_value(threshold)
    at.sidebar.checkbox[1].set_value(force_system2)
    at.run()
    return at


def screen_text(at: AppTest) -> str:
    parts = [e.value for kind in ("error", "warning", "success", "info") for e in getattr(at, kind)]
    parts += [m.value for m in at.markdown] + [str(m.value) for m in at.metric]
    parts += [c.value for c in at.caption]
    return "\n".join(str(p) for p in parts)


def verdict(ok: bool, detail: str) -> Result:
    return ("PASS" if ok else "FAIL"), detail


def geojson_mock(prompt=None, threshold=0.3, crop="Cotton") -> Dict[str, Any]:
    _, state, _ = run_pipeline_on_image(
        create_sample_field_image(),
        mock_mode=True,
        text_prompt=prompt,
        confidence_threshold=threshold,
        crop=crop,
    )
    return build_spray_geojson(state, crop=crop)


def labels_for(photo: str) -> Optional[List[Dict[str, Any]]]:
    for name in ("eval_manifest_v2.json", "eval_manifest_v2_holdout.json"):
        manifest = json.loads((PROJECT_ROOT / "data/manifests" / name).read_text())
        for item in manifest["items"]:
            if Path(item["image_path"]).name == Path(PHOTOS[photo][0]).name:
                return item["annotations"]
    return None


def approved_union(state: Dict[str, Any], shape: Tuple[int, int]) -> np.ndarray:
    payload = getattr((state.get("artifacts") or {}).get("spray_map"), "payload", None) or {}
    union = np.zeros(shape, dtype=bool)
    for zone in payload.get("approved_spray_zones", []):
        union |= np.asarray(zone["mask"], dtype=bool)
    return union


def real_photo(photo: str, **kwargs) -> Tuple[Image.Image, Dict[str, Any], Dict[str, Any], float]:
    path, crop = PHOTOS[photo]
    image = Image.open(PROJECT_ROOT / path).convert("RGB")
    start = time.perf_counter()
    _, state, kpis = run_pipeline_on_image(image, mock_mode=False, crop=crop, **kwargs)
    return image, state, kpis, time.perf_counter() - start


def plant_check(photo: str, image: Image.Image, state: Dict[str, Any]) -> Dict[str, Any]:
    annotations = labels_for(photo) or []
    rgb = np.asarray(image)
    crop_px, weed_px, crop_objects, weed_objects = ground_truth_masks(
        annotations, vegetation_mask(rgb)
    )
    sprayed = spray_footprint(approved_union(state, rgb.shape[:2]), 10)
    return spray_metrics(sprayed, crop_px, weed_px, crop_objects, weed_objects)


# ---------------------------------------------------------------- mock-mode cases (Sumant ST)


def st01() -> Result:
    text = screen_text(run_app())
    return verdict(
        "MOCK OUTPUT" in text and "REAL OUTPUT" not in text, f"MOCK banner={'MOCK OUTPUT' in text}"
    )


def st02() -> Result:
    at = run_app()
    infos = [i.value for i in at.info]
    has_lang = any(s.label == "Language" for s in at.selectbox)
    ok = any(str(i).startswith("This is test data") for i in infos) and has_lang
    return verdict(ok, f"summary starts 'This is test data'={ok}, Language selector={has_lang}")


def st03() -> Result:
    at = run_app(prompt="")
    errors = [e.value for e in at.error]
    ok = any("prompt is empty" in e for e in errors) and not at.metric
    return verdict(ok, f"errors={errors}, KPI cards shown={len(at.metric)}")


def st04() -> Result:
    seen = {}
    for crop in ("Sugar Beet", "Wheat", "Rice"):
        at = AppTest.from_file(APP, default_timeout=600)
        at.run()
        at.sidebar.selectbox[0].set_value(crop)
        at.run()
        seen[crop] = at.sidebar.text_input[0].value
    want = {
        "Sugar Beet": "weed . sugar beet plant .",
        "Wheat": "weed . wheat plant .",
        "Rice": "weed . rice plant .",
    }
    return verdict(seen == want, f"prompts {seen}")


def st05() -> Result:
    doc = geojson_mock(prompt="cotton . weed .")
    status = doc["metadata"]["status"]
    return verdict(
        not doc["features"] and status.startswith("No weed zones approved"),
        f"{len(doc['features'])} features, status '{status}'",
    )


def st06() -> Result:
    doc = geojson_mock(threshold=0.90)
    at = run_app(threshold=0.90)
    clusters = [m.value for m in at.metric if "Weed" in m.label and "Cluster" in m.label]
    conf = [f["properties"]["confidence"] for f in doc["features"]]
    return verdict(
        conf == [0.91] and clusters == ["1"],
        f"GeoJSON confidences {conf}, on-screen clusters {clusters}",
    )


def st07() -> Result:
    doc = geojson_mock()
    props = [f["properties"] for f in doc["features"]]
    meta = doc["metadata"]
    ok = (
        bool(props)
        and all("active_ingredient" not in p for p in props)
        and meta["statutory_status"] == "no_prescription"
        and "Not GPS" in meta["coordinate_note"]
    )
    return verdict(
        ok,
        f"{len(props)} features, herbicide fields={any('active_ingredient' in p for p in props)}, "
        f"statutory_status={meta['statutory_status']}, 'Not GPS'={'Not GPS' in meta['coordinate_note']}",
    )


def st08() -> Result:
    text = screen_text(run_app(force_system2=True))
    return verdict(
        "VERIFIED" not in text and "MOCK DIAGNOSIS" in text,
        f"'VERIFIED' shown={'VERIFIED' in text}, 'MOCK DIAGNOSIS' shown={'MOCK DIAGNOSIS' in text}",
    )


def st09() -> Result:
    rows = []
    for crop in ("Wheat", "Rice", "Sugar Beet"):
        text = screen_text(run_app(force_system2=True, crop=crop))
        rows.append((crop, "NO STATUTORY EVIDENCE FOUND" in text, "Pyrithiobac" in text))
    ok = all(banner and not cotton for _, banner, cotton in rows)
    return verdict(ok, "; ".join(f"{c}: banner={b}, Pyrithiobac={p}" for c, b, p in rows))


def st10() -> Result:
    try:
        decode_uploaded_image(b"This is a text file renamed to .jpg\n")
    except ImageDecodeError as exc:
        return verdict(True, f"ImageDecodeError: {exc}")
    return verdict(False, "a text file was accepted as an image")


def st11() -> Result:
    rng = np.random.default_rng(0)
    big = Image.fromarray(rng.integers(0, 255, (3000, 4000, 3), dtype=np.uint8))
    buf = io.BytesIO()
    big.save(buf, format="JPEG", quality=95)
    size_mb = buf.tell() / 1e6
    start = time.perf_counter()
    image = decode_uploaded_image(buf.getvalue())
    run_pipeline_on_image(image, mock_mode=True)
    return verdict(
        size_mb > 5,
        f"{size_mb:.1f} MB, 4000x3000, mock run {time.perf_counter() - start:.1f} s, no crash",
    )


# ---------------------------------------------------------------- real-mode cases


def st12() -> Result:
    start = time.perf_counter()
    at = run_app(mock=False)
    errors = [e.value for e in at.error]
    text = screen_text(at)
    return verdict(
        not errors and "REAL OUTPUT" in text,
        f"errors={errors}, REAL banner={'REAL OUTPUT' in text}, {time.perf_counter() - start:.0f} s",
    )


def st13() -> Result:
    image, state, kpis, seconds = real_photo("beet_X-10-0")
    m = plant_check("beet_X-10-0", image, state)
    ok = m["crop_plants_damaged"] == 0 and kpis["weed_count"] > 0
    return verdict(
        ok,
        f"{kpis['weed_count']} zones, crop plants touched {m['crop_plants_damaged']}/{m['crop_plants']}, "
        f"weeds hit {m['weed_plants_hit']}/{m['weed_plants']}, {seconds:.0f} s",
    )


def st14() -> Result:
    image, state, kpis, _ = real_photo("beet_X3-130-0")
    m = plant_check("beet_X3-130-0", image, state)
    sprayed_pct = m["sprayed_pct"]
    painted_pct = 100.0 * approved_union(state, np.asarray(image).shape[:2]).mean()
    image2, state2, _, _ = real_photo("beet_X2-30-0")
    m2 = plant_check("beet_X2-30-0", image2, state2)
    ok = sprayed_pct < 2 and m["crop_plants_damaged"] == 0
    return verdict(
        ok,
        f"X3-130-0: painted {painted_pct:.2f}% (with 10 px buffer {sprayed_pct:.2f}%), beet boxes "
        f"touched {m['crop_plants_damaged']}/{m['crop_plants']}; "
        f"X2-30-0 (known failure): beets touched {m2['crop_plants_damaged']}/{m2['crop_plants']}",
    )


def st15() -> Result:
    image, state, kpis, seconds = real_photo("cotton_CM_17")
    m = plant_check("cotton_CM_17", image, state)
    return "INFO", (
        f"no crash; {kpis['weed_count']} zones, weed pixels hit {m['weed_recall_pct']}%, "
        f"error={state.get('error')}, system2_error={state.get('system2_error')}, {seconds:.0f} s"
    )


def st16() -> Result:
    from src.agronomy.farmer_summary import farmer_summary
    from src.agronomy.providers import reasoning_provider

    _, state, _, _ = real_photo("beet_X-10-0")
    rows = []
    for language in ("Hindi", "Marathi"):
        time.sleep(GROQ_PAUSE_S)
        s = farmer_summary(
            state, "sugar beet", mock_mode=False, language=language, provider=reasoning_provider()
        )
        devanagari = any("ऀ" <= ch <= "ॿ" for ch in s["text"])
        rows.append((language, s["source"], devanagari))
    ok = all(src == "model" and dev for _, src, dev in rows)  # "groq" before 30 Oct
    return verdict(
        ok, "; ".join(f"{lang}: source={src}, Devanagari={dev}" for lang, src, dev in rows)
    )


def st17() -> Result:
    _, state, _, _ = real_photo("beet_X2-30-0")
    doc = build_spray_geojson(state, crop="Sugar Beet")
    labels = sorted({f["properties"]["target"] for f in doc["features"]})
    rings_closed = all(
        ring[0] == ring[-1]
        for f in doc["features"]
        for poly in f["geometry"]["coordinates"]
        for ring in poly
    )
    note = doc["metadata"]["coordinate_note"]
    ok = bool(doc["features"]) and rings_closed and "Not GPS" in note
    return verdict(
        ok,
        f"{len(doc['features'])} features {labels}, rings closed={rings_closed}, 'Not GPS'={'Not GPS' in note}",
    )


def st18() -> Result:
    _, state, _, seconds = real_photo("beet_X3-430-0")
    reviews = (state.get("spray_map") or {}).get("escalation") or []
    detail = ", ".join(f"{r.get('verdict')}:{r.get('p_weed')}" for r in reviews[:6])
    return (
        "INFO",
        f"{len(reviews)} agent reviews [{detail}] in {seconds:.0f} s (app real mode runs the agent)",
    )


def _subprocess_case(env_changes: Dict[str, str], force_system2: bool) -> Tuple[int, str]:
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from PIL import Image; from app.app import run_pipeline_on_image;"
        "from src.agronomy.farmer_summary import farmer_summary;"
        f"img = Image.open('{PHOTOS['beet_X-10-0'][0]}').convert('RGB');"
        f"_, s, k = run_pipeline_on_image(img, mock_mode=False, crop='Sugar Beet', force_system2={force_system2});"
        "print('RESULT', k['weed_count'], repr(s.get('error')), repr(str(s.get('system2_error'))[:80]),"
        " farmer_summary(s, 'sugar beet', mock_mode=False)['source'])"
    )
    env = {**os.environ, **env_changes}
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT")]
    return proc.returncode, (lines[-1] if lines else proc.stderr.strip().splitlines()[-1:])


def st19() -> Result:
    # No network for HTTP(S) clients: every proxy points at a closed local port.
    rc, line = _subprocess_case(
        {
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
            "http_proxy": "http://127.0.0.1:9",
        },
        force_system2=False,
    )
    return verdict(rc == 0 and str(line).startswith("RESULT"), f"exit {rc}: {line}")


def st20() -> Result:
    # Since 30 Oct the reasoning key is Cloudflare's; empty both so no provider can answer.
    rc, line = _subprocess_case(
        {"GROQ_API_KEY": "", "CLOUDFLARE_API_TOKEN": "", "CLOUDFLARE_ACCOUNT_ID": ""},
        force_system2=True,
    )
    return verdict(rc == 0 and str(line).startswith("RESULT"), f"exit {rc}: {line}")


def st21_22() -> Result:
    outs = {}
    for flag in ([], ["--no-plant-rules"]):
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/run_live_pipeline.py",
                "--image",
                PHOTOS["beet_X-10-0"][0],
                "--crop",
                "sugar beet",
                "--output",
                "/dev/null",
                *flag,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
        outs[" ".join(flag) or "default"] = proc.stdout
    a, b = outs["default"], outs["--no-plant-rules"]
    ok = (
        "detector=REAL, segmenter=REAL" in a
        and "Plant rules (green patches)" in a
        and "Summary for the farmer" in a
        and "No weed zones approved" in b
    )
    return verdict(
        ok,
        f"default: REAL/REAL={'detector=REAL, segmenter=REAL' in a}, plant rules line="
        f"{'Plant rules (green patches)' in a}; --no-plant-rules: 'No weed zones approved'="
        f"{'No weed zones approved' in b}",
    )


def main() -> int:
    cases: List[Tuple[str, Callable[[], Result]]] = [
        ("ST-01 MOCK banner", st01),
        ("ST-02 farmer summary in mock", st02),
        ("ST-03 empty prompt refused", st03),
        ("ST-04 crop switch resets prompt", st04),
        ("ST-05 prompt 'cotton . weed .'", st05),
        ("ST-06 slider 0.90", st06),
        ("ST-07 no herbicide without prescription", st07),
        ("ST-08 force System 2, cotton, mock", st08),
        ("ST-09 force System 2, other crops", st09),
        ("ST-10 fake .jpg", st10),
        ("ST-11 photo over 5 MB (mock)", st11),
    ]
    if "--real" in sys.argv:
        cases += [
            ("ST-12 real run in the app", st12),
            ("ST-13 beet_X-10-0: weeds only", st13),
            ("ST-14 weed-free photo; known failure", st14),
            ("ST-15 cotton_CM_17", st15),
            ("ST-16 Hindi / Marathi summary", st16),
            ("ST-17 real GeoJSON", st17),
            ("ST-18 escalation agent", st18),
            ("ST-19 no network", st19),
            ("ST-20 empty reasoning keys + force System 2", st20),
            ("ST-21/22 CLI with and without plant rules", st21_22),
        ]
    failures = 0
    for name, check in cases:
        start = time.perf_counter()
        try:
            status, detail = check()
        except Exception as exc:  # a crash is a failure of the case, not of the script
            status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
        failures += status == "FAIL"
        print(
            f"[{status}] {name} ({time.perf_counter() - start:.0f} s)\n       {detail}", flush=True
        )
    return failures


if __name__ == "__main__":
    sys.exit(main())
