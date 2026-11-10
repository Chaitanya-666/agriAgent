"""Base page: every locator is a data-testid, and every wait is an explicit condition."""

from __future__ import annotations

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

TIMEOUT = 10  # seconds; generous because the first analysis in a session loads the pipeline


def tid(test_id: str) -> tuple[str, str]:
    """Locator for an element by its data-testid attribute."""
    return By.CSS_SELECTOR, f'[data-testid="{test_id}"]'


class BasePage:
    def __init__(self, driver: WebDriver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        # The page redraws table rows after each action; retry instead of failing on an old copy.
        self.wait = WebDriverWait(driver, TIMEOUT, ignored_exceptions=[StaleElementReferenceException])

    def go(self, hash_: str = "") -> None:
        self.driver.get(f"{self.base_url}/{hash_}")
        self.wait.until(EC.text_to_be_present_in_element(tid("health-status"), "Service"))

    def el(self, test_id: str) -> WebElement:
        return self.wait.until(EC.presence_of_element_located(tid(test_id)))

    def visible(self, test_id: str) -> WebElement:
        return self.wait.until(EC.visibility_of_element_located(tid(test_id)))

    def is_visible(self, test_id: str) -> bool:
        found = self.driver.find_elements(*tid(test_id))
        return bool(found) and found[0].is_displayed()

    def click(self, test_id: str) -> None:
        self.wait.until(EC.element_to_be_clickable(tid(test_id))).click()

    def text(self, test_id: str) -> str:
        return self.visible(test_id).text

    def wait_text(self, test_id: str, expected: str) -> None:
        self.wait.until(EC.text_to_be_present_in_element(tid(test_id), expected))

    def health(self) -> str:
        return self.text("health-status")

    def tab(self, name: str) -> None:
        self.click(f"tab-{name}")
        self.visible(f"view-{name}")
