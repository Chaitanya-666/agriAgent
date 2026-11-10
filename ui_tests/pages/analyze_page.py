"""Analyze tab: choose a photo, set crop / mode / confidence, run, read the result card."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

from .base_page import BasePage, tid


class AnalyzePage(BasePage):
    def open(self) -> "AnalyzePage":
        self.go("#analyze")
        self.visible("analyze-form")
        return self

    def choose_file(self, path: Path) -> None:
        # A file input cannot be clicked headless; Selenium types the path into it instead.
        self.el("image-input").send_keys(str(Path(path).resolve()))
        self.wait_text("file-name", Path(path).name)

    def use_sample(self) -> None:
        self.click("use-sample")
        self.wait_text("file-name", "sample-field.png")

    def set_crop(self, crop: str) -> None:
        Select(self.el("crop-select")).select_by_value(crop)

    def set_mode(self, mode: str) -> None:
        Select(self.el("mode-select")).select_by_value(mode)

    def set_confidence(self, value: str) -> None:
        box = self.el("confidence-input")
        box.clear()
        if value:
            box.send_keys(value)

    def submit(self) -> None:
        self.click("analyze-button")

    def run(self) -> Dict[str, str]:
        """Submit and wait for a new result card; return what it shows."""
        before = self.driver.find_element(*tid("result-run-id")).get_attribute("textContent")
        self.submit()
        self.wait.until(lambda d: d.find_element(*tid("result")).is_displayed()
                        and d.find_element(*tid("result-run-id")).text not in ("", before))
        self.wait.until(lambda d: d.execute_script(
            "const i = document.querySelector('[data-testid=result-overlay]');"
            "return i.complete && i.naturalWidth > 0;"))
        return self.result()

    def result(self) -> Dict[str, str]:
        return {
            "run_id": self.text("result-run-id"),
            "safety_action": self.text("result-safety-action"),
            "status": self.text("result-status"),
            "weeds": self.text("kpi-weeds"),
            "withheld": self.text("kpi-withheld"),
            "infestation": self.text("kpi-infestation"),
            "savings": self.text("kpi-savings"),
            "duration": self.text("kpi-duration"),
            "geojson_href": self.el("download-geojson").get_attribute("href"),
        }

    def submit_expecting_error(self) -> str:
        self.submit()
        box = self.visible("form-error")
        self.wait.until(lambda d: box.text.strip() != "")
        # The button is re-enabled once the request (if any) has finished.
        self.wait.until(EC.element_to_be_clickable(tid("analyze-button")))
        return box.text

    def error_shown(self) -> bool:
        return self.is_visible("form-error")

    def real_mode_option(self):
        return self.el("mode-select").find_element("css selector", 'option[value="real"]')
