"""History tab: the runs table, crop filter, paging, detail panel and two-click delete."""

from __future__ import annotations

from typing import Dict, List

from selenium.webdriver.support.ui import Select

from .base_page import BasePage, tid

COLUMNS = ("id", "when", "file", "crop", "mode", "gate", "weeds", "infestation", "saved")


class HistoryPage(BasePage):
    def open(self) -> "HistoryPage":
        self.go("#history")
        self.visible("view-history")
        self.wait_loaded()
        return self

    def wait_loaded(self) -> None:
        self.wait.until(lambda d: d.find_element(*tid("history-total")).text.startswith("("))

    def total(self) -> int:
        self.wait_loaded()
        return int(self.text("history-total").strip("()").split()[0])

    def rows(self) -> List[Dict[str, str]]:
        out = []
        for tr in self.driver.find_elements(*tid("run-row")):
            cells = [td.text for td in tr.find_elements("tag name", "td")]
            row = dict(zip(COLUMNS, cells))
            row["run_id"] = tr.get_attribute("data-run-id")
            out.append(row)
        return out

    def wait_row_count(self, n: int) -> None:
        self.wait.until(lambda d: len(d.find_elements(*tid("run-row"))) == n)

    def filter_crop(self, crop: str) -> None:
        old = self.text("history-total")
        Select(self.el("history-crop-filter")).select_by_value(crop)
        self.wait.until(lambda d: d.find_element(*tid("history-total")).text != old
                        or all(r["crop"] == crop for r in self.rows()))

    def _row(self, run_id: str):
        return self.el("runs-table").find_element(
            "css selector", f'[data-testid="run-row"][data-run-id="{run_id}"]')

    def view(self, run_id: str) -> Dict[str, str]:
        self._row(run_id).find_element(*tid("view-run")).click()
        self.wait_text("detail-run-id", f"#{run_id}")
        dl = self.visible("detail-fields")
        terms = [dt.text for dt in dl.find_elements("tag name", "dt")]
        values = [dd.text for dd in dl.find_elements("tag name", "dd")]
        return dict(zip(terms, values))

    def delete_button(self, run_id: str):
        return self._row(run_id).find_element(*tid("delete-run"))

    def page_label(self) -> str:
        return self.text("page-label")

    def next_page(self) -> None:
        old = self.page_label()
        self.click("page-next")
        self.wait.until(lambda d: d.find_element(*tid("page-label")).text != old)

    def prev_page(self) -> None:
        old = self.page_label()
        self.click("page-prev")
        self.wait.until(lambda d: d.find_element(*tid("page-label")).text != old)
