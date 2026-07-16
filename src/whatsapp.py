"""WhatsApp Web automation module.

Provides a robust Playwright-based WhatsApp sender using persistent
browser profiles for session reuse. Only requires QR code scanning
on first run; subsequent runs reuse the saved login.
"""

from __future__ import annotations

import time as time_mod
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from src.config import AppConfig
from src.logger import get_logger, log_exception
from src.utils import ensure_directory, generate_screenshot_name, retry

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_logger = None


def _log():
    """Get the logger, initializing on first use."""
    global _logger
    if _logger is None:
        _logger = get_logger(__name__)
    return _logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WHATSAPP_URL = "https://web.whatsapp.com"
_SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "screenshots"

# Selectors - centralized for easy maintenance
_SELECTOR_SEARCH_INPUT = 'div[data-testid="chat-list-search-container"] input'
_SELECTOR_SEARCH_INPUT_ALT = 'div[contenteditable="true"][data-tab="3"]'
_SELECTOR_SEARCH_PLACEHOLDER = '[placeholder="Search or start a new chat"]'
_SELECTOR_SEARCH_SIDE = 'div[aria-label="Search or start a new chat"]'
_SELECTOR_CHAT_LIST = '[data-testid="chat-list"]'
_SELECTOR_CHAT_ITEM = '[data-testid*="list-item"]'
_SELECTOR_MESSAGE_INPUT = 'div[data-testid="conversation-compose-box-input"]'
_SELECTOR_MESSAGE_INPUT_ALT = 'div[role="textbox"][contenteditable="true"][data-tab="10"]'
_SELECTOR_SEND_BUTTON = 'button[data-testid="send"]'
_SELECTOR_POPUP_CONTINUE = 'div[data-testid="popup-controls-ok"]'
_SELECTOR_POPUP_CLOSE = 'button[aria-label="Close"]'
_SELECTOR_QR_CONTAINER = 'div[data-testid="qrcode"]'
_SELECTOR_LOGGED_IN = '[data-testid="chat-list"]'
_SELECTOR_PANEL_HEADER = '[data-testid="chatlist-header"]'
_SELECTOR_CHAT_PANEL = '[data-testid="conversation-header"]'
_SELECTOR_MESSAGE_LIST = '[data-testid="message-list"]'
_SELECTOR_MSG_IN = '[data-testid="msg-container"]'

# Timeouts (milliseconds)
_TIMEOUT_QR_SCAN = 180000  # 3 minutes for QR scanning
_TIMEOUT_LOGIN = 120000  # 2 minutes to detect login
_TIMEOUT_CHAT_LOAD = 15000  # 15 seconds for chat to load
_TIMEOUT_MESSAGE_SEND = 10000  # 10 seconds for message to send

# Retry configuration
_MAX_CHAT_RETRY = 2
_MAX_SEND_RETRY = 2
_RETRY_DELAY = 2.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WhatsAppException(Exception):
    """Base exception for WhatsApp automation errors."""


class LoginException(WhatsAppException):
    """Raised when login fails or times out."""


class ChatNotFoundException(WhatsAppException):
    """Raised when a chat cannot be found."""


class MessageSendException(WhatsAppException):
    """Raised when a message fails to send."""


# ---------------------------------------------------------------------------
# WhatsAppSender Class
# ---------------------------------------------------------------------------

class WhatsAppSender:
    """Automates WhatsApp Web messaging using Playwright.

    Uses a persistent browser profile to maintain login state across
    sessions. Only requires QR code scanning on first run.

    Attributes:
        config: Application configuration.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize the WhatsApp sender.

        Args:
            config: Application configuration with browser settings.
        """
        self.config = config
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None

    def launch_browser(self) -> None:
        """Launch Chromium with persistent WhatsApp profile.

        The profile stores login cookies and storage, so QR code
        scanning is only needed on first run.

        Raises:
            WhatsAppException: If browser fails to launch.
        """
        _log().info("Launching WhatsApp browser (headless={})", self.config.headless)

        try:
            self._playwright = sync_playwright().start()

            # Use a dedicated WhatsApp profile directory
            profile_path = ensure_directory(self.config.browser_profile / "whatsapp")

            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]

            # Use new headless mode for better compatibility with WhatsApp
            launch_kwargs = {
                "user_data_dir": str(profile_path),
                "headless": self.config.headless,
                "viewport": {"width": 1280, "height": 800},
                "args": args,
            }

            # Use channel=chrome for more stable headless sessions
            if self.config.headless:
                launch_kwargs["channel"] = "chrome"

            self._context = self._playwright.chromium.launch_persistent_context(
                **launch_kwargs,
            )

            _log().info("WhatsApp browser launched successfully")

        except Exception as exc:
            log_exception(exc, extra="WhatsApp browser launch")
            raise WhatsAppException(f"Failed to launch browser: {exc}") from exc

    def close_browser(self) -> None:
        """Close the browser and cleanup resources."""
        _log().info("Closing WhatsApp browser")

        try:
            if self._context:
                self._context.close()
                self._context = None

            if self._playwright:
                self._playwright.stop()
                self._playwright = None

            _log().info("WhatsApp browser closed successfully")

        except Exception as exc:
            _log().warning("Error closing browser: {}", str(exc))

    def _take_screenshot(self, page: Page, prefix: str, suffix: str = "") -> Path:
        """Take a screenshot and save it.

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

        try:
            page.screenshot(path=str(screenshot_path), full_page=False)
            _log().debug("Screenshot saved: {}", screenshot_path)
        except Exception as exc:
            _log().warning("Failed to take screenshot: {}", str(exc))

        return screenshot_path

    def _dismiss_popups(self, page: Page) -> None:
        """Dismiss any popup dialogs that may appear.

        Args:
            page: Playwright page instance.
        """
        # Try to dismiss "What's new" or other popups
        try:
            continue_btn = page.locator(_SELECTOR_POPUP_CONTINUE)
            if continue_btn.count() > 0 and continue_btn.is_visible():
                continue_btn.click()
                _log().info("Dismissed popup (Continue button)")
                time_mod.sleep(1)
        except Exception:
            pass

        try:
            close_btn = page.locator(_SELECTOR_POPUP_CLOSE)
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
                _log().info("Dismissed popup (Close button)")
                time_mod.sleep(1)
        except Exception:
            pass

    def ensure_logged_in(self) -> None:
        """Ensure the user is logged into WhatsApp Web.

        If not logged in, displays QR code and waits for scanning.
        Login is detected by the presence of the chat list/search box.

        Raises:
            LoginException: If login fails or times out.
        """
        if not self._context:
            raise WhatsAppException("Browser not launched. Call launch_browser() first.")

        page = self._context.new_page()

        try:
            _log().info("Opening WhatsApp Web")
            page.goto(_WHATSAPP_URL, wait_until="domcontentloaded", timeout=30000)

            # Wait for page to fully load
            time_mod.sleep(3)

            # Dismiss any initial popups
            self._dismiss_popups(page)

            # Check if already logged in (search box present)
            _log().info("Checking login status...")

            try:
                page.wait_for_selector(
                    _SELECTOR_LOGGED_IN,
                    timeout=5000,
                )
                _log().info("Already logged in - reusing session")
                return
            except Exception:
                _log().info("Not logged in, waiting for QR code scan...")

            # Check for QR code
            try:
                qr_element = page.locator(_SELECTOR_QR_CONTAINER)
                if qr_element.count() > 0:
                    _log().info("QR code detected - please scan with WhatsApp mobile")
                    print("\n" + "=" * 50)
                    print("Please scan the QR code with WhatsApp mobile app")
                    print("=" * 50 + "\n")
            except Exception:
                pass

            # Wait for login to complete (search box to appear)
            try:
                page.wait_for_selector(
                    _SELECTOR_LOGGED_IN,
                    timeout=_TIMEOUT_QR_SCAN,
                )
                _log().info("Login successful!")
                time_mod.sleep(2)  # Allow page to stabilize
            except Exception as exc:
                self._take_screenshot(page, "error", "login_timeout")
                raise LoginException(
                    f"Login timed out after {_TIMEOUT_QR_SCAN // 1000} seconds"
                ) from exc

        finally:
            page.close()

    def _find_chat(self, page: Page, chat_name: str) -> bool:
        """Search for and click on a chat by name.

        Args:
            page: Playwright page instance.
            chat_name: Name of the chat to find.

        Returns:
            True if chat was found and opened, False otherwise.
        """
        _log().info("Searching for chat: {}", chat_name)

        # Wait for page to be ready
        time_mod.sleep(2)

        # Find the search input with multiple fallback selectors
        search_input = None
        selectors = [
            _SELECTOR_SEARCH_PLACEHOLDER,
            _SELECTOR_SEARCH_INPUT,
            _SELECTOR_SEARCH_INPUT_ALT,
            _SELECTOR_SEARCH_SIDE,
            'input[placeholder*="Search"]',
            'div[contenteditable="true"]',
        ]

        for selector in selectors:
            try:
                elem = page.locator(selector)
                if elem.count() > 0 and elem.first.is_visible():
                    search_input = elem.first
                    _log().debug("Found search input with selector: {}", selector)
                    break
            except Exception:
                continue

        if search_input is None:
            _log().error("Could not find search input")
            return False

        # Clear and type chat name
        try:
            search_input.click()
            time_mod.sleep(0.5)
            # Use keyboard to clear and type
            page.keyboard.press("Control+a")
            page.keyboard.press("Backspace")
            time_mod.sleep(0.3)
            search_input.type(chat_name, delay=50)
        except Exception:
            # Fallback to fill
            search_input.fill("")
            search_input.fill(chat_name)

        # Wait for search results
        time_mod.sleep(3)

        # Method 1: Look for span with title matching chat_name, then click parent list-item
        try:
            chat_span = page.locator(f'span[title="{chat_name}"]')
            if chat_span.count() > 0:
                # Find the parent list-item element and click it
                parent_item = chat_span.first.locator(
                    'xpath=ancestor::div[contains(@data-testid,"list-item")]'
                )
                if parent_item.count() > 0:
                    parent_item.first.click()
                else:
                    chat_span.first.click()
                _log().info("Chat found and opened: {}", chat_name)
                # Wait for chat panel to load
                time_mod.sleep(3)
                # Verify chat opened
                for _ in range(3):
                    if page.locator(_SELECTOR_CHAT_PANEL).count() > 0:
                        return True
                    time_mod.sleep(1)
                return True
        except Exception:
            pass

        # Method 2: Look for list items and click the one containing chat_name
        try:
            chat_items = page.locator('[data-testid*="list-item"]').all()
            for item in chat_items:
                try:
                    text = item.inner_text()
                    if chat_name.lower() in text.lower():
                        item.click()
                        _log().info("Chat found (fallback) and opened: {}", chat_name)
                        time_mod.sleep(3)
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        # Method 3: Click on first search result (skip section headers)
        try:
            chat_items = page.locator('[data-testid*="list-item"]').all()
            for item in chat_items:
                try:
                    # Skip section headers like "Chats", "Contacts", etc.
                    text = item.inner_text().strip()
                    if text.lower() in ('chats', 'contacts', 'groups', 'unread'):
                        continue
                    if item.is_visible() and len(text) > 2:
                        item.click()
                        _log().info("Clicked first result for: {}", chat_name)
                        time_mod.sleep(3)
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        _log().warning("Chat not found: {}", chat_name)
        return False

    def _send_message_in_chat(self, page: Page, message: str) -> bool:
        """Type and send a message in the currently open chat.

        Args:
            page: Playwright page instance.
            message: Message text to send.

        Returns:
            True if message was sent successfully, False otherwise.
        """
        _log().info("Sending message (length={})", len(message))

        # Wait for chat to load
        time_mod.sleep(5)

        # Find the message input with multiple fallback selectors
        message_input = None
        selectors = [
            _SELECTOR_MESSAGE_INPUT,
            _SELECTOR_MESSAGE_INPUT_ALT,
            'div[role="textbox"][contenteditable="true"]',
            'footer div[contenteditable="true"]',
            'div[title="Type a message"]',
            '[data-tab="10"]',
        ]

        # Try each selector with retries
        for selector in selectors:
            for attempt in range(3):
                try:
                    elem = page.locator(selector)
                    if elem.count() > 0 and elem.first.is_visible():
                        message_input = elem.first
                        _log().debug("Found message input with selector: {} (attempt {})", selector, attempt + 1)
                        break
                    time_mod.sleep(1)
                except Exception:
                    time_mod.sleep(1)
                    continue
            if message_input is not None:
                break

        if message_input is None:
            _log().error("Could not find message input - taking screenshot for debugging")
            self._take_screenshot(page, "debug", "no_message_input")
            # Debug: print page info
            try:
                footer = page.locator('footer')
                _log().info("Footer count: {}, visible: {}", footer.count(), footer.first.is_visible() if footer.count() > 0 else False)
            except Exception:
                pass
            return False

        try:
            # Click to focus
            message_input.click()
            time_mod.sleep(0.5)

            # Type the message
            message_input.fill(message)
            time_mod.sleep(0.5)

            # Press Enter to send
            page.keyboard.press("Enter")
            time_mod.sleep(1)

            _log().info("Message sent successfully")
            return True

        except Exception as exc:
            _log().error("Failed to send message: {}", str(exc))
            return False

    def open_chat(self, chat_name: str) -> bool:
        """Open a WhatsApp chat by name.

        Args:
            chat_name: Name of the chat to open.

        Returns:
            True if chat was opened successfully, False otherwise.

        Raises:
            WhatsAppException: If browser not launched.
        """
        if not self._context:
            raise WhatsAppException("Browser not launched. Call launch_browser() first.")

        page = self._context.new_page()

        try:
            # Navigate to WhatsApp Web
            page.goto(_WHATSAPP_URL, wait_until="domcontentloaded", timeout=30000)
            time_mod.sleep(3)

            # Dismiss popups
            self._dismiss_popups(page)

            # Search and open chat
            return self._find_chat(page, chat_name)

        except Exception as exc:
            _log().error("Failed to open chat: {}", str(exc))
            return False
        finally:
            page.close()

    def send_message(self, chat_name: str, message: str) -> bool:
        """Send a message to a WhatsApp chat.

        This is the main public method for sending messages.

        Args:
            chat_name: Name of the chat (contact or group).
            message: Message text to send.

        Returns:
            True if message was sent successfully, False otherwise.

        Raises:
            WhatsAppException: If browser not launched.
        """
        start_time = time_mod.perf_counter()

        if not self._context:
            raise WhatsAppException("Browser not launched. Call launch_browser() first.")

        _log().info("Starting message send to: {}", chat_name)

        page = self._context.new_page()

        try:
            # Navigate to WhatsApp Web
            page.goto(_WHATSAPP_URL, wait_until="domcontentloaded", timeout=30000)
            time_mod.sleep(3)

            # Dismiss popups
            self._dismiss_popups(page)

            # Find and open the chat with retry
            chat_opened = False
            for attempt in range(1, _MAX_CHAT_RETRY + 1):
                chat_opened = self._find_chat(page, chat_name)
                if chat_opened:
                    break
                if attempt < _MAX_CHAT_RETRY:
                    _log().info("Retrying chat search (attempt {})", attempt + 1)
                    time_mod.sleep(2)

            if not chat_opened:
                self._take_screenshot(page, "error", "chat_not_found")
                raise ChatNotFoundException(f"Chat not found: {chat_name}")

            # Send message with retry
            message_sent = False
            for attempt in range(1, _MAX_SEND_RETRY + 1):
                message_sent = self._send_message_in_chat(page, message)
                if message_sent:
                    break
                if attempt < _MAX_SEND_RETRY:
                    _log().info("Retrying message send (attempt {})", attempt + 1)
                    time_mod.sleep(2)

            if not message_sent:
                self._take_screenshot(page, "error", "send_failed")
                raise MessageSendException(f"Failed to send message to: {chat_name}")

            duration = time_mod.perf_counter() - start_time
            _log().info(
                "Message sent to {} in {:.2f}s",
                chat_name,
                duration,
            )
            return True

        except (ChatNotFoundException, MessageSendException):
            raise

        except Exception as exc:
            duration = time_mod.perf_counter() - start_time
            _log().error(
                "Failed to send message to {} after {:.2f}s: {}",
                chat_name,
                duration,
                str(exc),
            )
            self._take_screenshot(page, "error", "exception")
            raise WhatsAppException(f"Failed to send message: {exc}") from exc

        finally:
            page.close()

    def send_test_message(self) -> bool:
        """Send a test message to 'Saved Messages'.

        Convenience method for testing the WhatsApp connection.

        Returns:
            True if test message was sent successfully.
        """
        test_message = (
            f"Hello from SBPDCL Monitor\n"
            f"Test message sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return self.send_message("Saved Messages", test_message)

    def send_message_to_phone(self, phone: str, message: str) -> bool:
        """Send a message directly to a phone number.

        Uses WhatsApp's search to find the contact by phone number.

        Args:
            phone: Phone number with country code (e.g., "+91XXXXXXXXXX").
            message: Message text to send.

        Returns:
            True if message was sent successfully, False otherwise.

        Raises:
            WhatsAppException: If browser not launched.
        """
        start_time = time_mod.perf_counter()

        if not self._context:
            raise WhatsAppException("Browser not launched. Call launch_browser() first.")

        # Clean phone number (remove +, spaces, dashes)
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")

        _log().info("Starting message send to phone: {}", phone)

        page = self._context.new_page()

        try:
            # Navigate to WhatsApp Web
            page.goto(_WHATSAPP_URL, wait_until="domcontentloaded", timeout=30000)
            time_mod.sleep(3)

            # Dismiss popups
            self._dismiss_popups(page)

            # Search for the phone number
            _log().info("Searching for phone: {}", clean_phone)
            chat_opened = self._find_chat(page, clean_phone)

            if not chat_opened:
                self._take_screenshot(page, "error", "phone_not_found")
                raise ChatNotFoundException(
                    f"Could not find chat for phone: {phone}"
                )

            # Send message with retry
            message_sent = False
            for attempt in range(1, _MAX_SEND_RETRY + 1):
                message_sent = self._send_message_in_chat(page, message)
                if message_sent:
                    break
                if attempt < _MAX_SEND_RETRY:
                    _log().info("Retrying message send (attempt {})", attempt + 1)
                    time_mod.sleep(2)

            if not message_sent:
                self._take_screenshot(page, "error", "send_failed")
                raise MessageSendException(f"Failed to send message to: {phone}")

            duration = time_mod.perf_counter() - start_time
            _log().info(
                "Message sent to {} in {:.2f}s",
                phone,
                duration,
            )
            return True

        except (ChatNotFoundException, MessageSendException):
            raise

        except Exception as exc:
            duration = time_mod.perf_counter() - start_time
            _log().error(
                "Failed to send message to {} after {:.2f}s: {}",
                phone,
                duration,
                str(exc),
            )
            self._take_screenshot(page, "error", "exception")
            raise WhatsAppException(f"Failed to send message: {exc}") from exc

        finally:
            page.close()

    def send_notification(
        self,
        chat_name: str,
        phone: str,
        message: str,
    ) -> bool:
        """Send a notification to a phone number.

        Searches for the contact by phone number in WhatsApp.

        Args:
            chat_name: Not used (kept for compatibility).
            phone: Phone number with country code.
            message: Message text to send.

        Returns:
            True if message was sent successfully, False otherwise.
        """
        # Search by phone number
        if phone:
            return self.send_message_to_phone(phone, message)

        _log().error("No valid phone provided")
        return False

    # -------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------

    def __enter__(self) -> WhatsAppSender:
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

    # Add parent directory to path for self-test
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from src.config import load_config

    print("=" * 60)
    print("WHATSAPP SENDER SELF TEST")
    print("=" * 60)

    try:
        # Load configuration
        config = load_config()

        print("\nLaunching WhatsApp browser...")
        with WhatsAppSender(config) as sender:
            print("Ensuring login...")
            sender.ensure_logged_in()

            # Test 1: Send to Saved Messages
            print("\n[Test 1] Sending to 'Saved Messages'...")
            result = sender.send_test_message()
            if result:
                print("  ✓ Test message sent to Saved Messages!")
            else:
                print("  ✗ Failed to send to Saved Messages")

            # Test 2: Send to phone number (if configured)
            if config.consumers and config.consumers[0].phone:
                consumer = config.consumers[0]
                print(f"\n[Test 2] Sending to phone: {consumer.phone}...")
                test_msg = f"Test from SBPDCL Monitor at {datetime.now().strftime('%H:%M:%S')}"
                result = sender.send_message_to_phone(consumer.phone, test_msg)
                if result:
                    print(f"  ✓ Message sent to {consumer.phone}!")
                else:
                    print(f"  ✗ Failed to send to {consumer.phone}")

    except WhatsAppException as exc:
        print(f"\nError: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 60)
    print("WHATSAPP SENDER TEST COMPLETE")
    print("=" * 60)
