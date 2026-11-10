"""Stats, navigation and layout cases FT-20, FT-22, FT-23 (Lab 4 sheet, automated in Lab 7)."""

import pytest

from pages import AnalyzePage, HistoryPage, StatsPage


@pytest.mark.smoke
@pytest.mark.regression
@pytest.mark.ft("FT-20")
def test_ft20_stats_match_history(driver, base_url, seed_runs, snap):
    seed_runs(3, crop="cotton")
    seed_runs(2, crop="wheat")
    page = StatsPage(driver, base_url).open()
    totals = page.totals()
    assert totals["total-runs"] == "5"
    assert totals["total-weeds"] == "15"  # mock mode: 3 per run
    assert totals["suppressed"] == "0"
    assert [row[:3] for row in page.by_crop()] == [["cotton", "3", "9"], ["wheat", "2", "6"]]
    snap("FT-20")


@pytest.mark.regression
@pytest.mark.ft("FT-22")
def test_ft22_deep_link_and_tabs(driver, base_url, snap):
    page = HistoryPage(driver, base_url)
    page.go("#history")
    assert page.is_visible("view-history") and not page.is_visible("view-analyze")
    assert "active" in page.el("tab-history").get_attribute("class")
    page.tab("stats")
    assert driver.current_url.endswith("#stats")
    driver.back()
    page.visible("view-history")
    snap("FT-22")


@pytest.mark.regression
@pytest.mark.ft("FT-23")
def test_ft23_phone_width_has_no_sideways_scroll(driver, base_url, snap):
    driver.set_window_size(390, 844)
    page = AnalyzePage(driver, base_url).open()
    page.use_sample()
    page.run()
    overflow = driver.execute_script(
        "return document.documentElement.scrollWidth - document.documentElement.clientWidth;")
    assert overflow <= 0, f"page is {overflow}px wider than the screen"
    snap("FT-23")
