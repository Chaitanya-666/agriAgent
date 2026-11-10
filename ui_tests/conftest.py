"""Fixtures for the Field Service UI suite (Software Testing Lab 7).

    .venv/bin/python -m pytest ui_tests                 # starts its own server, headless Chromium
    .venv/bin/python -m pytest ui_tests -m smoke        # smoke run only
    .venv/bin/python -m pytest ui_tests --headed        # watch the browser
    .venv/bin/python -m pytest ui_tests --base-url http://127.0.0.1:8000   # existing server

Every test starts from an empty history (the `clean_db` fixture deletes all runs through the
public API), so tests never depend on each other or on their order.
"""

from __future__ import annotations

import base64
import io
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, WebDriverException

REPO = Path(__file__).resolve().parent.parent
REPORT_DIR = REPO / "ui_tests" / "reports"
SHOT_DIR = REPORT_DIR / "screenshots"


def pytest_addoption(parser):
    parser.addoption("--base-url", default=None, help="use a running Field Service instead of starting one")
    parser.addoption("--headed", action="store_true", help="show the browser window")
    parser.addoption("--chrome-binary", default=os.environ.get("CHROME_BINARY", "/usr/bin/chromium"))
    parser.addoption("--chromedriver", default=os.environ.get("CHROMEDRIVER", "/usr/bin/chromedriver"))


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: main happy paths, quick to run")
    config.addinivalue_line("markers", "regression: full set, including negative and boundary cases")
    config.addinivalue_line("markers", "ft(id): functional test case ID from the Lab 4 sheet")
    SHOT_DIR.mkdir(parents=True, exist_ok=True)


# ---------- server ----------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(request, tmp_path_factory):
    given = request.config.getoption("--base-url")
    if given:
        yield given.rstrip("/")
        return
    port = _free_port()
    db = tmp_path_factory.mktemp("ui-db") / "ui.db"
    log = open(tmp_path_factory.mktemp("ui-log") / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--factory", "service.main:create_app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=REPO, env={**os.environ, "AGRIAGENT_DB": str(db)}, stdout=log, stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/api/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise RuntimeError(f"Field Service exited early, see {log.name}")
        time.sleep(0.2)  # polling a process that is starting; not a wait inside a test
    else:
        proc.kill()
        raise RuntimeError("Field Service did not start in 30 s")
    yield url
    proc.terminate()
    proc.wait(timeout=10)
    log.close()


@pytest.fixture
def api(base_url):
    with httpx.Client(base_url=base_url, timeout=30) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_db(api):
    """Delete every run before each test (through the API, as a user could)."""
    while True:
        items = api.get("/api/runs", params={"limit": 100}).json()["items"]
        if not items:
            break
        for run in items:
            api.delete(f"/api/runs/{run['id']}")


# ---------- browser ----------

@pytest.fixture
def driver(request):
    options = webdriver.ChromeOptions()
    options.binary_location = request.config.getoption("--chrome-binary")
    if not request.config.getoption("--headed"):
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,1000")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    service = webdriver.ChromeService(request.config.getoption("--chromedriver"))
    drv = webdriver.Chrome(options=options, service=service)
    yield drv
    drv.quit()


def full_page_screenshot(driver, path: Path, max_height: int = 2400) -> None:
    """Whole page, not just the visible window (Chrome DevTools Protocol)."""
    size = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})["cssContentSize"]
    clip = {"x": 0, "y": 0, "width": size["width"], "height": min(size["height"], max_height), "scale": 1}
    shot = driver.execute_cdp_cmd(
        "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True, "clip": clip})
    path.write_bytes(base64.b64decode(shot["data"]))


@pytest.fixture
def snap(driver, request):
    """snap("FT-02") saves a full-page evidence screenshot as reports/screenshots/FT-02.png."""
    def take(name: str) -> Path:
        path = SHOT_DIR / f"{name}.png"
        full_page_screenshot(driver, path)
        request.node.user_properties.append(("evidence", str(path)))
        return path
    return take


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    extras = getattr(report, "extras", [])
    html = item.config.pluginmanager.getplugin("html")
    drv = item.funcargs.get("driver")
    if report.failed and drv is not None:
        # A failing page may have an alert open (FT-21 catches injected script that way); a
        # screenshot with an open alert raises, so close it first, and never let a screenshot
        # problem replace the real test result.
        try:
            try:
                alert = drv.switch_to.alert
                report.sections.append(("browser alert", f"open alert closed: {alert.text!r}"))
                alert.dismiss()
            except NoAlertPresentException:
                pass
            path = SHOT_DIR / f"FAILED_{item.name}.png"
            drv.save_screenshot(str(path))
            if html:
                extras.append(html.extras.image(str(path.relative_to(REPORT_DIR))))
        except WebDriverException as exc:
            report.sections.append(("screenshot", f"no screenshot: {exc.msg}"))
    elif html:
        for key, value in report.user_properties:
            if key == "evidence":
                extras.append(html.extras.image(str(Path(value).relative_to(REPORT_DIR))))
    report.extras = extras


# ---------- test files ----------

@pytest.fixture(scope="session")
def files(tmp_path_factory):
    """Upload files for the cases: a real field photo, a JPEG, a tiny PNG, a fake PNG and a
    PNG whose file name is HTML (for the script-injection case)."""
    d = tmp_path_factory.mktemp("uploads")
    out = {"photo": REPO / "tests" / "fixtures" / "sample" / "beet_X-10-0.png"}
    Image.open(out["photo"]).convert("RGB").resize((320, 320)).save(d / "field.jpg", quality=85)
    out["jpeg"] = d / "field.jpg"
    Image.new("RGB", (20, 20), (90, 160, 60)).save(d / "tiny.png")
    out["tiny"] = d / "tiny.png"
    (d / "notes.png").write_text("this is a text file with a .png name\n")
    out["fake_png"] = d / "notes.png"
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 95, 70)).save(buf, format="PNG")
    out["html_name"] = d / "<img src=x onerror=alert(1)>.png"
    out["html_name"].write_bytes(buf.getvalue())
    return out


@pytest.fixture
def seed_runs(api, files):
    """Create runs directly through the API (faster than the UI) for history/stats cases."""
    def make(n: int, crop: str = "cotton") -> list[int]:
        ids = []
        raw = files["jpeg"].read_bytes()
        for _ in range(n):
            r = api.post("/api/analyze", files={"image": ("field.jpg", raw, "image/jpeg")},
                         data={"crop": crop})
            assert r.status_code == 201, r.text
            ids.append(r.json()["id"])
        return ids
    return make
