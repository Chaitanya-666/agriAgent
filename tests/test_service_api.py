"""API tests for service/main.py through FastAPI's TestClient. IDs: UT-A-xx.

These run the real pipeline in mock mode (about 6 ms per image) against a temporary SQLite
file, so they need no GPU, no network and no model weights. Real mode is exercised by
patching the pipeline call, which checks the routing without loading the models.
"""

import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image

from service import analysis, config
from service.config import Settings
from service.main import create_app

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample" / "beet_X-10-0.png"


def png(width=320, height=240, color=(120, 95, 70)):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def jpeg(width=320, height=240):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (120, 95, 70)).save(buf, format="JPEG")
    return buf.getvalue()


class ApiTestCase(unittest.TestCase):
    allow_real = False

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.app = create_app(Settings(db_path=Path(self._tmp.name) / "api.db",
                                       allow_real_mode=self.allow_real))
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self._tmp.cleanup()

    def analyze(self, raw=None, filename="field.png", **form):
        files = {"image": (filename, png() if raw is None else raw, "image/png")}
        return self.client.post("/api/analyze", files=files, data=form)

    def assertError(self, response, status, code, field=None):
        self.assertEqual(response.status_code, status, response.text)
        error = response.json()["error"]
        self.assertEqual(error["code"], code)
        if field is not None:
            self.assertEqual(error["field"], field)
        self.assertTrue(error["message"])


class HealthTests(ApiTestCase):
    def test_health_reports_status_modes_and_limits(self):  # UT-A-01
        body = self.client.get("/api/health").json()
        self.assertEqual((body["status"], body["database"]), ("ok", "up"))
        self.assertEqual(body["modes"], {"mock": True, "real": False})
        self.assertEqual(body["crops"], list(config.CROPS))
        self.assertEqual(body["limits"]["min_confidence"], [0.70, 1.00])

    def test_sample_image_is_a_png(self):  # UT-A-02
        r = self.client.get("/api/sample-image")
        self.assertEqual(r.headers["content-type"], "image/png")
        self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_web_page_is_served(self):  # UT-A-03
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("AgriAgent Field Service", r.text)


class AnalyzeHappyPathTests(ApiTestCase):
    def test_png_upload_creates_a_run(self):  # UT-A-04
        r = self.analyze(crop="cotton")
        self.assertEqual(r.status_code, 201, r.text)
        run = r.json()
        self.assertEqual((run["id"], run["crop"], run["mode"]), (1, "cotton", "mock"))
        self.assertEqual((run["width"], run["height"]), (320, 240))
        self.assertEqual(run["safety_action"], "ACCEPT")
        self.assertEqual(run["weed_count"], 3)  # mock mode always returns 3 fixed boxes
        self.assertTrue(0 <= run["infestation_pct"] <= 100)
        self.assertEqual(len(run["image_sha256"]), 64)
        self.assertEqual(run["links"]["overlay"], "/api/runs/1/overlay.jpg")
        self.assertEqual(self.client.get("/api/runs/1").json()["filename"], "field.png")

    def test_jpeg_upload(self):  # UT-A-05
        r = self.analyze(raw=jpeg(), filename="field.jpg")
        self.assertEqual(r.status_code, 201, r.text)

    def test_real_field_photo_fixture(self):  # UT-A-06
        r = self.analyze(raw=FIXTURE.read_bytes(), filename=FIXTURE.name, crop="sugar beet")
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()["width"], r.json()["height"]), (640, 640))

    def test_confidence_boundaries_accepted(self):  # UT-A-07 (BVA)
        for value in ("0.70", "1.00"):
            with self.subTest(value=value):
                r = self.analyze(min_confidence=value)
                self.assertEqual(r.status_code, 201, r.text)
                self.assertAlmostEqual(r.json()["min_confidence"], float(value))

    def test_defaults_when_form_fields_are_left_out(self):  # UT-A-08
        run = self.analyze().json()
        self.assertEqual((run["crop"], run["mode"], run["min_confidence"]), ("cotton", "mock", 0.70))

    def test_same_image_gives_same_hash(self):  # UT-A-09
        a = self.analyze().json()["image_sha256"]
        b = self.analyze().json()["image_sha256"]
        c = self.analyze(raw=png(color=(1, 2, 3))).json()["image_sha256"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_user_text_is_returned_as_data(self):  # UT-A-10
        name = "<img src=x onerror=alert(1)>.png"
        run = self.analyze(filename=name).json()
        self.assertEqual(run["filename"], name)  # the web page must escape it (it uses textContent)
        long_name = "a" * 300 + ".png"
        self.assertEqual(len(self.analyze(filename=long_name).json()["filename"]), 255)


class AnalyzeErrorTests(ApiTestCase):
    def test_missing_image(self):  # UT-A-11
        r = self.client.post("/api/analyze", data={"crop": "cotton"})
        self.assertError(r, 422, "missing_image", "image")

    def test_invalid_crop(self):  # UT-A-12
        self.assertError(self.analyze(crop="maize"), 422, "invalid_crop", "crop")

    def test_confidence_just_outside_and_nan(self):  # UT-A-13 (BVA + Lab 2 NaN defect)
        for value in ("0.69", "1.01", "nan", "inf", "abc"):
            with self.subTest(value=value):
                self.assertError(self.analyze(min_confidence=value), 422,
                                 "invalid_min_confidence", "min_confidence")

    def test_real_mode_refused_when_switched_off(self):  # UT-A-14
        self.assertError(self.analyze(mode="real"), 403, "real_mode_disabled", "mode")

    def test_non_image_file(self):  # UT-A-15
        self.assertError(self.analyze(raw=b"name,crop\nx,cotton\n", filename="data.png"),
                         415, "unsupported_type", "image")

    def test_file_over_the_size_limit(self):  # UT-A-16
        raw = png()
        with mock.patch.object(config, "MAX_UPLOAD_BYTES", len(raw) - 1):  # one byte over
            self.assertError(self.analyze(raw=raw), 413, "file_too_large", "image")
        with mock.patch.object(config, "MAX_UPLOAD_BYTES", len(raw)):  # exactly at the limit
            self.assertEqual(self.analyze(raw=raw).status_code, 201)

    def test_tiny_image(self):  # UT-A-17
        self.assertError(self.analyze(raw=png(31, 31)), 422, "image_too_small", "image")

    def test_pipeline_failure_returns_500_and_stores_nothing(self):  # UT-A-18
        with mock.patch.object(analysis, "_run_pipeline", side_effect=RuntimeError("model crashed")), \
                self.assertLogs("agriagent.service", level="ERROR") as logs:
            r = self.analyze()
        self.assertIn("analysis failed", logs.output[0])
        self.assertError(r, 500, "analysis_failed")
        self.assertIn("model crashed", r.json()["error"]["message"])
        self.assertEqual(self.client.get("/api/runs").json()["total"], 0)

    def test_nothing_is_stored_for_refused_requests(self):  # UT-A-19
        self.analyze(crop="maize")
        self.analyze(min_confidence="0.5")
        self.analyze(raw=b"nope")
        self.assertEqual(self.client.get("/api/stats").json()["total_runs"], 0)


class RealModeRoutingTests(ApiTestCase):
    allow_real = True

    def test_real_mode_goes_through_the_lock_with_mock_false(self):  # UT-A-20
        original = analysis._run_pipeline
        calls = []

        def fake(image, params, mock):
            calls.append((mock, analysis._REAL_MODE_LOCK.locked()))
            return original(image, params, mock=True)  # stand-in: no GPU in unit tests

        with mock.patch.object(analysis, "_run_pipeline", side_effect=fake):
            r = self.analyze(mode="real")
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["mode"], "real")
        self.assertEqual(calls, [(False, True)])  # real path, lock held while it ran
        self.assertFalse(analysis._REAL_MODE_LOCK.locked())

    def test_health_shows_real_mode_on(self):  # UT-A-21
        self.assertTrue(self.client.get("/api/health").json()["modes"]["real"])


class RunsTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        for crop in ("cotton", "wheat", "cotton"):
            self.assertEqual(self.analyze(crop=crop).status_code, 201)

    def test_list_is_newest_first(self):  # UT-A-22
        body = self.client.get("/api/runs").json()
        self.assertEqual([r["id"] for r in body["items"]], [3, 2, 1])
        self.assertEqual((body["total"], body["limit"], body["offset"]), (3, 20, 0))

    def test_paging_and_crop_filter(self):  # UT-A-23
        page = self.client.get("/api/runs?limit=2&offset=2").json()
        self.assertEqual(([r["id"] for r in page["items"]], page["total"]), ([1], 3))
        cotton = self.client.get("/api/runs?crop=Cotton").json()
        self.assertEqual(([r["id"] for r in cotton["items"]], cotton["total"]), ([3, 1], 2))

    def test_bad_paging_values(self):  # UT-A-24 (BVA on limit)
        self.assertError(self.client.get("/api/runs?limit=0"), 422, "invalid_limit", "limit")
        self.assertError(self.client.get("/api/runs?limit=101"), 422, "invalid_limit", "limit")
        self.assertEqual(self.client.get("/api/runs?limit=100").status_code, 200)
        self.assertError(self.client.get("/api/runs?offset=-1"), 422, "invalid_offset", "offset")
        self.assertError(self.client.get("/api/runs?limit=ten"), 422, "invalid_request", "limit")
        self.assertError(self.client.get("/api/runs?crop=maize"), 422, "invalid_crop", "crop")

    def test_get_one_and_missing(self):  # UT-A-25
        self.assertEqual(self.client.get("/api/runs/2").json()["crop"], "wheat")
        self.assertError(self.client.get("/api/runs/99"), 404, "not_found")
        self.assertError(self.client.get("/api/runs/abc"), 422, "invalid_request", "run_id")

    def test_overlay_is_a_jpeg(self):  # UT-A-26
        r = self.client.get("/api/runs/1/overlay.jpg")
        self.assertEqual(r.headers["content-type"], "image/jpeg")
        self.assertTrue(r.content.startswith(b"\xff\xd8"))
        self.assertError(self.client.get("/api/runs/99/overlay.jpg"), 404, "not_found")

    def test_geojson_download(self):  # UT-A-27
        r = self.client.get("/api/runs/1/spray-map.geojson")
        self.assertEqual(r.headers["content-type"], "application/geo+json")
        self.assertIn("spray-map-run-1.geojson", r.headers["content-disposition"])
        doc = json.loads(r.text)
        self.assertEqual(doc["type"], "FeatureCollection")
        self.assertEqual(doc["metadata"]["crop"], "cotton")
        self.assertError(self.client.get("/api/runs/99/spray-map.geojson"), 404, "not_found")

    def test_delete(self):  # UT-A-28
        self.assertEqual(self.client.delete("/api/runs/2").status_code, 204)
        self.assertError(self.client.get("/api/runs/2"), 404, "not_found")
        self.assertError(self.client.delete("/api/runs/2"), 404, "not_found")
        self.assertEqual(self.client.get("/api/runs").json()["total"], 2)

    def test_stats(self):  # UT-A-29
        s = self.client.get("/api/stats").json()
        self.assertEqual((s["total_runs"], s["total_weeds"]), (3, 9))
        self.assertEqual(s["by_crop"][0]["crop"], "cotton")
        self.assertEqual(s["by_safety_action"], [{"safety_action": "ACCEPT", "runs": 3}])

    def test_unknown_route_and_wrong_method(self):  # UT-A-30
        self.assertError(self.client.get("/api/nothing-here"), 404, "not_found")
        self.assertError(self.client.put("/api/runs/1"), 405, "method_not_allowed")


class ConcurrencyTests(ApiTestCase):
    def test_parallel_uploads_all_stored_with_unique_ids(self):  # UT-A-31
        results, errors = [], []

        def worker():
            try:
                with TestClient(self.app) as c:
                    r = c.post("/api/analyze", files={"image": ("p.png", png(), "image/png")})
                    results.append((r.status_code, r.json().get("id")))
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(s for s, _ in results), [201] * 12)
        self.assertEqual(len({i for _, i in results}), 12)
        self.assertEqual(self.client.get("/api/stats").json()["total_runs"], 12)


if __name__ == "__main__":
    unittest.main()
