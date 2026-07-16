"""Debug WhatsApp selectors."""
import sys
import io
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright


def main():
    profile_dir = Path("browser/whatsapp")
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
        )

        page = context.new_page()
        page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # Take screenshot
        page.screenshot(path="screenshots/whatsapp_debug.png")

        # Try different selectors
        print("Testing selectors:")

        selectors = [
            '[placeholder="Search or start a new chat"]',
            'div[data-testid="chat-list-search-container"] input',
            'div[contenteditable="true"][data-tab="3"]',
            'div[aria-label="Search or start a new chat"]',
            'input[placeholder*="Search"]',
            'div[contenteditable="true"]',
            "side",
        ]

        for sel in selectors:
            try:
                elem = page.locator(sel)
                count = elem.count()
                visible = elem.first.is_visible() if count > 0 else False
                print(f"  {sel}: count={count}, visible={visible}")
            except Exception as e:
                print(f"  {sel}: ERROR - {e}")

        context.close()


if __name__ == "__main__":
    main()
