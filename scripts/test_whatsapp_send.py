"""Test WhatsApp send functionality."""
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

        print("Looking for search input...")
        search_input = page.locator('[placeholder="Search or start a new chat"]')
        print(f"Search input found: {search_input.count() > 0}")

        if search_input.count() > 0:
            print("Clicking search input...")
            search_input.click()
            time.sleep(1)

            print("Typing 'Saved Messages'...")
            search_input.type("Saved Messages", delay=50)
            time.sleep(3)

            # Take screenshot after typing
            page.screenshot(path="screenshots/whatsapp_after_search.png")

            # Look for results
            print("Looking for chat results...")
            results = page.locator('[data-testid*="list-item"]')
            print(f"Results found: {results.count()}")

            # Also try span with title
            span_results = page.locator('span[title="Saved Messages"]')
            print(f"Span results found: {span_results.count()}")

            # Try to click first result if available
            if results.count() > 0:
                print("Clicking first result...")
                results.first.click()
                time.sleep(3)
                page.screenshot(path="screenshots/whatsapp_chat_opened.png")
                print("Chat opened!")
            elif span_results.count() > 0:
                print("Clicking span result...")
                span_results.first.click()
                time.sleep(3)
                page.screenshot(path="screenshots/whatsapp_chat_opened.png")
                print("Chat opened!")
            else:
                print("No results found")

        context.close()


if __name__ == "__main__":
    main()
