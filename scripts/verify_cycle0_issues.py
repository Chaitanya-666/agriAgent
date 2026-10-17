"""Re-run Amit's Cycle 0 failing test cases (GitHub issues #6-#13) against the current code.

Screen checks drive the real app/app.py headlessly with Streamlit's AppTest, setting the
sidebar exactly as each test case did. GeoJSON checks call the same functions the app's
download button uses. Real-mode checks need the model weights and take about a minute.

Usage:
    python scripts/verify_cycle0_issues.py            # mock-mode cases only
    python scripts/verify_cycle0_issues.py --real     # also TC-15 and the blank image in real mode
"""

import io
import sys
from pathlib import Path
from typing import Callable, List, Tuple

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

APP = str(PROJECT_ROOT / "app/app.py")


def run_app(prompt=None, threshold=None, force_system2=False, crop="Cotton", mock=True) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=600)
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
    return "\n".join(str(p) for p in parts)


def geojson(prompt=None, threshold=0.3, force_system2=False, crop="Cotton", image=None):
    image = image or create_sample_field_image()
    _, state, _ = run_pipeline_on_image(
        image, mock_mode=True, text_prompt=prompt, confidence_threshold=threshold,
        crop=crop, force_system2=force_system2,
    )
    return build_spray_geojson(state, crop=crop)


def tc03_issue7() -> Tuple[bool, str]:
    doc = geojson()
    props = [f["properties"] for f in doc["features"]]
    ok = bool(props) and all("active_ingredient" not in p for p in props)
    return ok, f"{len(props)} features, herbicide fields present: {any('active_ingredient' in p for p in props)}"


def tc04_issue8() -> Tuple[bool, str]:
    doc = geojson(prompt="cotton . weed .")
    status = doc["metadata"]["status"]
    return len(doc["features"]) == 0 and status.startswith("No weed zones approved"), (
        f"{len(doc['features'])} features, status '{status}'"
    )


def tc07_issue6() -> Tuple[bool, str]:
    at = run_app(prompt="")
    errors = [e.value for e in at.error]
    ok = any("prompt is empty" in e for e in errors) and not at.metric
    return ok, f"errors={errors}, KPI cards shown={len(at.metric)}"


def tc08_issue9() -> Tuple[bool, str]:
    doc = geojson(threshold=0.90)
    at = run_app(threshold=0.90)
    clusters = [m.value for m in at.metric if "Weed" in m.label and "Cluster" in m.label]
    confidences = [f["properties"]["confidence"] for f in doc["features"]]
    ok = confidences == [0.91] and clusters == ["1"]
    return ok, f"GeoJSON confidences {confidences}, on-screen weed clusters {clusters}"


def tc10_issue10() -> Tuple[bool, str]:
    at = run_app(force_system2=True)
    text = screen_text(at)
    ok = "VERIFIED" not in text and "MOCK DIAGNOSIS" in text and "MOCK OUTPUT" in text
    return ok, f"'VERIFIED' on screen: {'VERIFIED' in text}; mock warnings: {'MOCK DIAGNOSIS' in text}, {'MOCK OUTPUT' in text}"


def tc11_issue11() -> Tuple[bool, str]:
    results = []
    for crop in ("Wheat", "Rice", "Sugar Beet"):
        text = screen_text(run_app(force_system2=True, crop=crop))
        results.append((crop, "Pyrithiobac" in text, "NO STATUTORY EVIDENCE" in text))
    ok = all(not cotton for _, cotton, _ in results)
    return ok, "; ".join(f"{c}: cotton herbicide={p}, no-evidence banner={n}" for c, p, n in results)


def tc13_issue12() -> Tuple[bool, str]:
    corrupt_rejected = False
    try:
        decode_uploaded_image(b"\xff\xd8\xff\xe0 not really a jpeg")
    except ImageDecodeError:
        corrupt_rejected = True
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), "white").save(buf, format="JPEG")
    blank_decodes = decode_uploaded_image(buf.getvalue()).size == (640, 480)
    mock_labelled = "MOCK OUTPUT" in screen_text(run_app())
    ok = corrupt_rejected and blank_decodes and mock_labelled
    return ok, (f"corrupt bytes rejected={corrupt_rejected}, blank white JPG is a valid image={blank_decodes}, "
                f"mock results labelled MOCK={mock_labelled}")


def tc15_issue13_real() -> Tuple[bool, str]:
    at = run_app(mock=False)
    errors = [e.value for e in at.error]
    text = screen_text(at)
    ok = not errors and "REAL OUTPUT" in text
    return ok, f"errors={errors}, REAL badge shown={'REAL OUTPUT' in text}"


def blank_image_real() -> Tuple[bool, str]:
    _, state, kpis = run_pipeline_on_image(Image.new("RGB", (640, 480), "white"), mock_mode=False)
    return kpis["weed_count"] == 0, f"real models on a blank white image: {len(state['boxes'])} boxes, {kpis['weed_count']} sprayed zones"


def main() -> int:
    cases: List[Tuple[str, Callable[[], Tuple[bool, str]]]] = [
        ("#7  TC-03 herbicide in GeoJSON with System 2 off", tc03_issue7),
        ("#8  TC-04 status with 0 features", tc04_issue8),
        ("#6  TC-07 empty prompt", tc07_issue6),
        ("#9  TC-08 slider at 0.90", tc08_issue9),
        ("#10 TC-10 mock diagnosis shown as approved", tc10_issue10),
        ("#11 TC-11 cotton herbicide for other crops", tc11_issue11),
        ("#12 TC-13 blank / corrupt image", tc13_issue12),
    ]
    if "--real" in sys.argv:
        cases += [
            ("#13 TC-15 real mode in the app", tc15_issue13_real),
            ("#12 blank image in real mode", blank_image_real),
        ]
    failures = 0
    for name, check in cases:
        ok, detail = check()
        failures += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}\n       {detail}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
