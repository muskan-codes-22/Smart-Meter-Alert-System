"""Script to inspect WhatsApp Web page structure."""
import sys
import io
import time
import tempfile
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        # Use persistent profile
        profile_dir = Path(tempfile.mkdtemp()) / "whatsapp_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
        )

        page = context.new_page()
        page.goto("https://web.whatsapp.com", timeout=60000)

        print("Waiting for WhatsApp Web to load...")
        print("If QR code appears, please scan it.")
        print("Waiting up to 120 seconds for login...")

        # Wait for either QR code or chat list
        try:
            # Check for QR code first
            qr_frame = page.frame_locator('iframe[src*="auth"]')
            print("QR code frame detected - please scan")

            # Wait for main page to load (after login)
            # Look for search box which appears after login
            page.wait_for_selector('[data-testid="chat-list"]', timeout=120000)
            print("Login successful!")
        except Exception as e:
            print(f"Timeout or error: {e}")

        # Take screenshot
        page.screenshot(path="screenshots/whatsapp_inspection.png")

        # Get all elements with data-testid
        elements = page.query_selector_all("[data-testid]")
        print("\nElements with data-testid:")
        for elem in elements[:50]:  # Limit to first 50
            testid = elem.get_attribute("data-testid")
            tag = elem.evaluate("el => el.tagName")
            print(f"  {tag}: {testid}")

        # Get search-related elements
        print("\nSearch-related elements:")
        search_elements = page.query_selector_all('[data-testid*="search"], [placeholder*="Search"], [aria-label*="Search"]')
        for elem in search_elements:
            testid = elem.get_attribute("data-testid")
            placeholder = elem.get_attribute("placeholder")
            aria_label = elem.get_attribute("aria-label")
            print(f"  testid={testid}, placeholder={placeholder}, aria-label={aria_label}")

        # Get chat list elements
        print("\nChat list elements:")
        chat_elements = page.query_selector_all('[data-testid*="chat"]')
        for elem in chat_elements[:20]:
            testid = elem.get_attribute("data-testid")
            print(f"  testid={testid}")

        context.close()


if __name__ == "__main__":
    main()
