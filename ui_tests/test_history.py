"""History tab cases FT-15 to FT-19 and FT-21 (Lab 4 functional sheet, automated in Lab 7)."""

import pytest
from selenium.common.exceptions import NoAlertPresentException

from pages import AnalyzePage, HistoryPage


@pytest.mark.smoke
@pytest.mark.regression
@pytest.mark.ft("FT-15")
def test_ft15_history_lists_runs_newest_first(driver, base_url, seed_runs, snap):
    ids = seed_runs(3)
    page = HistoryPage(driver, base_url).open()
    assert page.total() == 3
    assert [r["run_id"] for r in page.rows()] == [str(i) for i in reversed(ids)]
    assert all(r["gate"] == "ACCEPT" and r["weeds"] == "3" for r in page.rows())
    snap("FT-15")


@pytest.mark.regression
@pytest.mark.ft("FT-16")
def test_ft16_crop_filter(driver, base_url, seed_runs, snap):
    seed_runs(2, crop="cotton")
    beet = seed_runs(1, crop="sugar beet")
    page = HistoryPage(driver, base_url).open()
    page.filter_crop("sugar beet")
    page.wait_row_count(1)
    assert [r["run_id"] for r in page.rows()] == [str(beet[0])]
    assert page.total() == 1
    snap("FT-16")
    page.filter_crop("")
    page.wait_row_count(3)


@pytest.mark.regression
@pytest.mark.ft("FT-17")
def test_ft17_view_detail_matches_result_card(driver, base_url, snap):
    analyze = AnalyzePage(driver, base_url).open()
    analyze.use_sample()
    card = analyze.run()
    run_id = card["run_id"].lstrip("#")
    details = HistoryPage(driver, base_url).open().view(run_id)
    assert details["Safety gate"] == card["safety_action"]
    assert details["Weeds approved"] == card["weeds"]
    assert details["Infestation"] == card["infestation"]
    assert details["Chemical saved"] == card["savings"]
    assert details["File"] == "sample-field.png"
    assert len(details["SHA-256"]) == 64
    snap("FT-17")


@pytest.mark.regression
@pytest.mark.ft("FT-18")
def test_ft18_delete_needs_two_clicks(driver, base_url, seed_runs, api, snap):
    keep, remove = seed_runs(2)
    page = HistoryPage(driver, base_url).open()
    page.delete_button(str(remove)).click()
    page.wait.until(lambda d: page.delete_button(str(remove)).text == "Confirm delete")
    assert page.total() == 2  # first click only arms the button
    snap("FT-18a")
    page.delete_button(str(remove)).click()
    page.wait_row_count(1)
    assert [r["run_id"] for r in page.rows()] == [str(keep)]
    assert api.get(f"/api/runs/{remove}").status_code == 404
    snap("FT-18")


@pytest.mark.regression
@pytest.mark.ft("FT-19")
def test_ft19_paging_ten_per_page(driver, base_url, seed_runs, snap):
    ids = seed_runs(12)
    page = HistoryPage(driver, base_url).open()
    page.wait_row_count(10)
    assert page.page_label() == "Page 1 of 2"
    assert not page.el("page-prev").is_enabled()
    page.next_page()
    page.wait_row_count(2)
    assert page.page_label() == "Page 2 of 2"
    assert [r["run_id"] for r in page.rows()] == [str(ids[1]), str(ids[0])]
    assert not page.el("page-next").is_enabled()
    snap("FT-19")
    page.prev_page()
    page.wait_row_count(10)


@pytest.mark.regression
@pytest.mark.ft("FT-21")
def test_ft21_html_in_a_file_name_is_shown_as_text(driver, base_url, files, snap):
    analyze = AnalyzePage(driver, base_url).open()
    analyze.choose_file(files["html_name"])
    run_id = analyze.run()["run_id"].lstrip("#")
    page = HistoryPage(driver, base_url).open()
    row = next(r for r in page.rows() if r["run_id"] == run_id)
    assert row["file"] == "<img src=x onerror=alert(1)>.png"  # literal text, not an image tag
    assert driver.find_elements("css selector", "#runs-body img") == []
    with pytest.raises(NoAlertPresentException):
        driver.switch_to.alert.text  # the onerror script never ran
    snap("FT-21")
