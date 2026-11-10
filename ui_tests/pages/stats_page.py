"""Stats tab: totals and the per-crop table."""

from __future__ import annotations

from typing import Dict, List

from .base_page import BasePage, tid


class StatsPage(BasePage):
    def open(self) -> "StatsPage":
        self.go("#stats")
        self.visible("view-stats")
        self.wait.until(lambda d: d.find_element(*tid("stat-total-runs")).text != "")
        return self

    def totals(self) -> Dict[str, str]:
        return {k: self.text(f"stat-{k}") for k in
                ("total-runs", "total-weeds", "avg-infestation", "avg-savings", "suppressed")}

    def by_crop(self) -> List[List[str]]:
        return [[td.text for td in tr.find_elements("tag name", "td")]
                for tr in self.driver.find_elements(*tid("stats-crop-row"))]
