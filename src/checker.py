"""SBPDCL Balance Checker Module.

Automates the process of checking electricity balance from the SBPDCL
(South Bihar Power Distribution Company Limited) portal using Playwright.
"""

from __future__ import annotations

import re
import time as time_mod
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from src.config import AppConfig
from src.logger import get_logger, log_exception
from src.models import BalanceResult, Consumer
from src.utils import (
    ensure_directory,
    generate_screenshot_name,
    mask_ca_number,
    retry,
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SBPDCL_URL = "https://wss.sbpdcl.co.in/cportal/#/guest/secure/searchbill"
_SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "screenshots"

# Selectors - centralized for easy updates if website changes
_SELECTOR_CA_INPUT = "input#mat-input-0"
_SELECTOR_SEARCH_BUTTON = 'button:has-text("Search")'
_SELECTOR_INVALID_CA_ERROR = 'text="Invalid CA number"'
_SELECTOR_BALANCE_TEXT = "text=/Available Balance/i"
_SELECTOR_BALANCE_VALUE = ".bill-amount, .balance-amount, [class*=balance]"
_SELECTOR_AVAILABLE_BALANCE = 'text="Available Balance(Rs)"'

# Retry configuration
_MAX_PAGE_LOAD_RETRIES = 3
_MAX_BALANCE_RETRIES = 3
_MAX_BROWSER_LAUNCH_RETRIES = 2
_RETRY_DELAY = 2.0
_RETRY_BACKOFF = 2.0


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class SBPDCLException(Exception):
    """Base exception for SBPDCL checker errors."""


class PageLoadException(SBPDCLException):
    """Raised when the SBPDCL page fails to load."""


class BalanceNotFoundException(SBPDCLException):
    """Raised when balance cannot be extracted from the page."""


class InvalidCANumberException(SBPDCLException):
    """Raised when the CA number is invalid."""


# ---------------------------------------------------------------------------
# SBPDCLChecker Class
# ---------------------------------------------------------------------------

class SBPDCLChecker:
    """Automates balance checking from the SBPDCL portal.

    Uses Playwright to navigate the SBPDCL website, enter the consumer's
    CA number, and extract the available balance.

    Attributes:
        config: Application configuration.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize the SBPDCL checker.

        Args:
            config: Application configuration with browser settings.
        """
        self.config = config
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def launch_browser(self) -> None:
        """Launch the Chromium browser with persistent profile.

        Retries up to _MAX_BROWSER_LAUNCH_RETRIES times on failure.

        Raises:
            SBPDCLException: If browser cannot be launched after retries.
        """
        logger.info("Launching browser (headless={})", self.config.headless)

        for attempt in range(1, _MAX_BROWSER_LAUNCH_RETRIES + 1):
            try:
                self._playwright = sync_playwright().start()

                # Ensure browser profile directory exists
                profile_path = ensure_directory(self.config.browser_profile)

                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_path),
                    headless=self.config.headless,
                    viewport={"width": 1280, "height": 720},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )

                logger.info(
                    "Browser launched successfully (attempt {})",
                    attempt,
                )
                return

            except Exception as exc:
                logger.warning(
                    "Browser launch attempt {} failed: {}",
                    attempt,
                    str(exc),
                )

                if attempt == _MAX_BROWSER_LAUNCH_RETRIES:
                    log_exception(exc, extra="browser launch")
                    raise SBPDCLException(
                        f"Failed to launch browser after {_MAX_BROWSER_LAUNCH_RETRIES} attempts"
                    ) from exc

                time_mod.sleep(_RETRY_DELAY)

    def close_browser(self) -> None:
        """Close the browser and cleanup resources."""
        logger.info("Closing browser")

        try:
            if self._context:
                self._context.close()
                self._context = None

            if self._playwright:
                self._playwright.stop()
                self._playwright = None

            logger.info("Browser closed successfully")

        except Exception as exc:
            logger.warning("Error closing browser: {}", str(exc))

    def _take_screenshot(self, page: Page, prefix: str, suffix: str = "") -> Path:
        """Take a screenshot and save it to the screenshots directory.

        Args:
            page: Playwright page instance.
            prefix: Screenshot filename prefix.
            suffix: Optional suffix for the filename.

        Returns:
            Path to the saved screenshot.
        """
        ensure_directory(_SCREENSHOT_DIR)
        filename = generate_screenshot_name(prefix, suffix)
        screenshot_path = _SCREENSHOT_DIR / filename

        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info("Screenshot saved: {}", screenshot_path)

        return screenshot_path

    @retry(
        max_attempts=_MAX_PAGE_LOAD_RETRIES,
        delay=_RETRY_DELAY,
        backoff=_RETRY_BACKOFF,
        exceptions=(Exception,),
    )
    def _navigate_to_page(self, page: Page) -> None:
        """Navigate to the SBPDCL search bill page.

        Args:
            page: Playwright page instance.

        Raises:
            PageLoadException: If page fails to load after retries.
        """
        logger.info("Navigating to SBPDCL portal")
        page.goto(_SBPDCL_URL, wait_until="networkidle", timeout=30000)

        # Wait for the Angular app to render
        page.wait_for_selector(_SELECTOR_CA_INPUT, timeout=15000)
        logger.info("Page loaded successfully")

    def _enter_ca_number(self, page: Page, ca_number: str) -> None:
        """Enter the CA number into the search field.

        Args:
            page: Playwright page instance.
            ca_number: Consumer Account number to enter.
        """
        masked_ca = mask_ca_number(ca_number)
        logger.info("Entering CA number: {}", masked_ca)

        ca_input = page.locator(_SELECTOR_CA_INPUT)
        ca_input.wait_for(state="visible", timeout=10000)

        # Clear existing text and enter CA number
        ca_input.click()
        ca_input.fill("")
        ca_input.fill(ca_number)

        logger.debug("CA number entered")

    def _click_search(self, page: Page) -> None:
        """Click the Search button.

        Args:
            page: Playwright page instance.
        """
        logger.info("Clicking Search button")

        search_button = page.locator(_SELECTOR_SEARCH_BUTTON)
        search_button.wait_for(state="visible", timeout=10000)
        search_button.click()

        logger.debug("Search button clicked")

    def _check_for_invalid_ca(self, page: Page) -> bool:
        """Check if the page shows an invalid CA number error.

        Args:
            page: Playwright page instance.

        Returns:
            True if invalid CA error is displayed.
        """
        try:
            error_locator = page.locator(_SELECTOR_INVALID_CA_ERROR)
            return error_locator.count() > 0 and error_locator.is_visible()
        except Exception:
            return False

    @retry(
        max_attempts=_MAX_BALANCE_RETRIES,
        delay=_RETRY_DELAY,
        backoff=_RETRY_BACKOFF,
        exceptions=(BalanceNotFoundException,),
    )
    def _extract_balance(self, page: Page) -> float:
        """Extract the available balance amount from the results page.

        Specifically targets "Available Balance(Rs)" field which contains
        the current available balance for prepaid meters.

        Args:
            page: Playwright page instance.

        Returns:
            Balance amount as float.

        Raises:
            BalanceNotFoundException: If balance cannot be extracted.
        """
        logger.info("Extracting balance from page")

        # Wait for results to load
        page.wait_for_load_state("networkidle", timeout=10000)
        time_mod.sleep(2)  # Allow Angular to finish rendering

        # Get full page text for debugging
        page_text = page.inner_text("body")
        logger.debug("Page text length: {} chars", len(page_text))

        # Strategy 1: Look for "Available Balance(Rs)" pattern (primary target)
        # The page shows: "Available Balance(Rs)" followed by "₹568.07"
        available_balance_patterns = [
            r"Available\s+Balance\s*\(Rs\)\s*[₹]?\s*([\d,]+\.?\d*)",
            r"Available\s+Balance\s*\(Rs\)\s*\n?\s*[₹]?([\d,]+\.?\d*)",
        ]

        for pattern in available_balance_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
            if match:
                balance_str = match.group(1).replace(",", "")
                try:
                    balance = float(balance_str)
                    logger.info("Available Balance found: ₹{:.2f}", balance)
                    return balance
                except ValueError:
                    continue

        # Strategy 2: Use Playwright to find the exact element
        try:
            # Look for the label "Available Balance(Rs)" and get the value from the same row
            balance_label = page.locator('text="Available Balance(Rs)"')
            if balance_label.count() > 0:
                # Get the parent row and extract the value
                row = balance_label.locator("xpath=ancestor::tr")
                if row.count() > 0:
                    # Get all cells in the row
                    cells = row.locator("td").all()
                    for cell in cells:
                        text = cell.inner_text().strip()
                        match = re.search(r"[₹]?\s*([\d,]+\.?\d*)", text)
                        if match:
                            balance_str = match.group(1).replace(",", "")
                            balance = float(balance_str)
                            logger.info(
                                "Balance found from table row: ₹{:.2f}",
                                balance,
                            )
                            return balance
        except Exception as exc:
            logger.debug("Table row extraction failed: {}", str(exc))

        # Strategy 3: Look for "Available Balance" with Rs suffix in page text
        try:
            pattern = r"Available\s+Balance[^₹]*[₹]?\s*([\d,]+\.?\d*)"
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                balance_str = match.group(1).replace(",", "")
                balance = float(balance_str)
                logger.info("Balance found with fallback pattern: ₹{:.2f}", balance)
                return balance
        except Exception as exc:
            logger.debug("Fallback pattern failed: {}", str(exc))

        # Strategy 4: Look for balance in specific CSS class elements
        try:
            balance_elements = page.locator(_SELECTOR_BALANCE_VALUE).all()
            for elem in balance_elements:
                text = elem.inner_text()
                match = re.search(r"[\d,]+\.?\d*", text)
                if match:
                    balance_str = match.group(0).replace(",", "")
                    balance = float(balance_str)
                    logger.info("Balance found from element: ₹{:.2f}", balance)
                    return balance
        except Exception as exc:
            logger.debug("Element-based balance extraction failed: {}", str(exc))

        raise BalanceNotFoundException(
            "Could not extract Available Balance from page. "
            "Page structure may have changed."
        )

    def check_balance(self, consumer: Consumer) -> BalanceResult:
        """Check the balance for a consumer.

        This is the main public method that orchestrates the entire
        balance checking workflow.

        Args:
            consumer: Consumer information including CA number.

        Returns:
            BalanceResult with the extracted balance and status.

        Raises:
            SBPDCLException: If any step in the workflow fails.
        """
        start_time = time_mod.perf_counter()
        masked_ca = mask_ca_number(consumer.ca)

        logger.info(
            "Starting balance check for {} (CA: {})",
            consumer.name,
            masked_ca,
        )

        if not self._context:
            raise SBPDCLException("Browser not launched. Call launch_browser() first.")

        page: Optional[Page] = None
        screenshot_path: Optional[Path] = None

        try:
            # Create a new page
            page = self._context.new_page()
            page.set_default_timeout(self.config.default_timeout)

            # Navigate to SBPDCL portal
            self._navigate_to_page(page)

            # Enter CA number
            self._enter_ca_number(page, consumer.ca)

            # Click Search
            self._click_search(page)

            # Wait for results
            page.wait_for_load_state("networkidle", timeout=15000)
            time_mod.sleep(2)

            # Check for invalid CA number
            if self._check_for_invalid_ca(page):
                screenshot_path = self._take_screenshot(
                    page, "error", "invalid_ca"
                )
                raise InvalidCANumberException(
                    f"Invalid CA number for consumer {consumer.name}"
                )

            # Extract balance
            balance = self._extract_balance(page)

            # Take success screenshot
            screenshot_path = self._take_screenshot(page, "balance", "success")

            duration = time_mod.perf_counter() - start_time
            logger.info(
                "Balance check completed for {} in {:.2f}s: ₹{:.2f}",
                consumer.name,
                duration,
                balance,
            )

            return BalanceResult(
                consumer=consumer,
                balance=balance,
                status="success",
                checked_at=datetime.now(),
            )

        except (InvalidCANumberException, BalanceNotFoundException):
            raise

        except Exception as exc:
            duration = time_mod.perf_counter() - start_time
            logger.error(
                "Balance check failed for {} after {:.2f}s: {}",
                consumer.name,
                duration,
                str(exc),
            )

            # Take error screenshot if page is available
            if page:
                try:
                    screenshot_path = self._take_screenshot(
                        page, "error", "exception"
                    )
                except Exception:
                    pass

            log_exception(exc, extra=f"balance check for {consumer.name}")

            raise SBPDCLException(
                f"Failed to check balance for {consumer.name}: {exc}"
            ) from exc

        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    # -------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------

    def __enter__(self) -> SBPDCLChecker:
        """Enter context manager."""
        self.launch_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.close_browser()


# ---------------------------------------------------------------------------
# Self Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import io

    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    from src.config import load_config

    print("=" * 60)
    print("SBPDCL CHECKER SELF TEST")
    print("=" * 60)

    try:
        # Load configuration
        config = load_config()

        if not config.consumers:
            print("No consumers configured. Add consumers to data/consumers.json")
            sys.exit(1)

        # Get first consumer
        consumer_data = config.consumers[0]
        consumer = Consumer(
            name=consumer_data.name,
            ca=consumer_data.ca,
            threshold=consumer_data.threshold,
            whatsapp=consumer_data.whatsapp,
        )

        print(f"\nConsumer: {consumer.name}")
        print(f"CA Number: {mask_ca_number(consumer.ca)}")

        # Check balance
        print("\nChecking balance...")
        with SBPDCLChecker(config) as checker:
            result = checker.check_balance(consumer)

        print(f"\n{'='*60}")
        print(f"Result: {result}")
        print(f"Balance: ₹{result.balance:.2f}")
        print(f"Status: {result.status}")
        print(f"Checked at: {result.checked_at}")
        print(f"Is low: {result.is_low}")
        print(f"{'='*60}")

    except SBPDCLException as exc:
        print(f"\nError: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        sys.exit(1)
