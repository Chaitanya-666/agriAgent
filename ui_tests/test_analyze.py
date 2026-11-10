"""Analyze tab cases FT-01 to FT-14 (Lab 4 functional sheet, automated in Lab 7).

Design: EP on the input classes (valid photo / no photo / non-image / too-small image,
supported crop, mock vs disabled real mode) and BVA on min confidence (0.69 / 0.70 / 1.00 / 1.01).
"""

import json

import httpx
import pytest

from pages import AnalyzePage, HistoryPage


@pytest.mark.smoke
@pytest.mark.regression
@pytest.mark.ft("FT-01")
def test_ft01_page_loads_and_service_is_online(driver, base_url, snap):
    page = AnalyzePage(driver, base_url).open()
    assert page.health() == "Service online"
    assert page.text("version").startswith("v")
    assert page.el("crop-select").get_attribute("value") == "cotton"
    assert page.el("confidence-input").get_attribute("value") == "0.70"
    snap("FT-01")


@pytest.mark.smoke
@pytest.mark.regression
@pytest.mark.ft("FT-02")
def test_ft02_sample_image_happy_path(driver, base_url, snap):
    page = AnalyzePage(driver, base_url).open()
    page.use_sample()
    result = page.run()
    assert result["run_id"].startswith("#")
    assert result["safety_action"] == "ACCEPT"
    assert result["weeds"] == "3"
    assert "Selective Spot-Spray Prescription Generated" in result["status"]
    assert result["infestation"].endswith("%") and result["savings"].endswith("%")
    snap("FT-02")


@pytest.mark.regression
@pytest.mark.ft("FT-03")
def test_ft03_upload_png_photo_with_sugar_beet(driver, base_url, files, snap):
    page = AnalyzePage(driver, base_url).open()
    page.choose_file(files["photo"])
    assert page.is_visible("preview")
    page.set_crop("sugar beet")
    run_id = page.run()["run_id"].lstrip("#")
    snap("FT-03")
    history = HistoryPage(driver, base_url).open()
    row = next(r for r in history.rows() if r["run_id"] == run_id)
    assert (row["file"], row["crop"], row["mode"]) == (files["photo"].name, "sugar beet", "mock")


@pytest.mark.regression
@pytest.mark.ft("FT-04")
def test_ft04_upload_jpeg(driver, base_url, files, snap):
    page = AnalyzePage(driver, base_url).open()
    page.choose_file(files["jpeg"])
    assert page.run()["safety_action"] == "ACCEPT"
    snap("FT-04")


@pytest.mark.regression
@pytest.mark.ft("FT-05")
def test_ft05_no_file_chosen(driver, base_url, api, snap):
    page = AnalyzePage(driver, base_url).open()
    message = page.submit_expecting_error()
    assert message == "Choose a field photo or use the sample image first."
    assert not page.is_visible("result")
    assert api.get("/api/runs").json()["total"] == 0  # nothing was sent
    snap("FT-05")


@pytest.mark.regression
@pytest.mark.parametrize("value, case", [("0.69", "FT-06"), ("1.01", "FT-09")])
def test_ft06_ft09_confidence_just_outside_range_is_refused(driver, base_url, api, snap, value, case):
    page = AnalyzePage(driver, base_url).open()
    page.use_sample()
    page.set_confidence(value)
    assert page.submit_expecting_error() == "Min confidence must be between 0.70 and 1.00."
    assert api.get("/api/runs").json()["total"] == 0
    snap(case)


@pytest.mark.regression
@pytest.mark.parametrize("value, case", [("0.70", "FT-07"), ("1.00", "FT-08")])
def test_ft07_ft08_confidence_boundaries_are_accepted(driver, base_url, api, snap, value, case):
    page = AnalyzePage(driver, base_url).open()
    page.use_sample()
    page.set_confidence(value)
    run_id = page.run()["run_id"].lstrip("#")
    assert api.get(f"/api/runs/{run_id}").json()["min_confidence"] == float(value)
    snap(case)


@pytest.mark.regression
@pytest.mark.ft("FT-10")
def test_ft10_empty_confidence_uses_server_default(driver, base_url, api, snap):
    page = AnalyzePage(driver, base_url).open()
    page.use_sample()
    page.set_confidence("")
    run_id = page.run()["run_id"].lstrip("#")
    assert api.get(f"/api/runs/{run_id}").json()["min_confidence"] == 0.70
    snap("FT-10")


@pytest.mark.regression
@pytest.mark.ft("FT-11")
def test_ft11_text_file_named_png_is_refused_by_the_server(driver, base_url, files, api, snap):
    page = AnalyzePage(driver, base_url).open()
    page.choose_file(files["fake_png"])
    assert page.submit_expecting_error() == "only PNG and JPEG images are accepted"
    assert api.get("/api/runs").json()["total"] == 0
    snap("FT-11")


@pytest.mark.regression
@pytest.mark.ft("FT-12")
def test_ft12_image_smaller_than_32px_is_refused(driver, base_url, files, snap):
    page = AnalyzePage(driver, base_url).open()
    page.choose_file(files["tiny"])
    message = page.submit_expecting_error()
    assert "20x20" in message and "at least 32 pixels" in message
    snap("FT-12")


@pytest.mark.regression
@pytest.mark.ft("FT-13")
def test_ft13_real_mode_is_disabled_when_the_server_is_in_mock_only(driver, base_url, snap):
    page = AnalyzePage(driver, base_url).open()
    option = page.real_mode_option()
    assert option.get_attribute("disabled") is not None
    assert "(off on this server)" in option.text
    snap("FT-13")


@pytest.mark.regression
@pytest.mark.ft("FT-14")
def test_ft14_geojson_download_link(driver, base_url, snap):
    page = AnalyzePage(driver, base_url).open()
    page.use_sample()
    result = page.run()
    run_id = result["run_id"].lstrip("#")
    assert result["geojson_href"].endswith(f"/api/runs/{run_id}/spray-map.geojson")
    r = httpx.get(result["geojson_href"], timeout=10)  # what the browser would save
    assert r.headers["content-type"] == "application/geo+json"
    assert f"spray-map-run-{run_id}.geojson" in r.headers["content-disposition"]
    doc = json.loads(r.text)
    assert doc["type"] == "FeatureCollection" and len(doc["features"]) >= 1
    snap("FT-14")
