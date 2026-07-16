"""Script to inspect the SBPDCL page structure."""
import sys
import io
import time

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(
            "https://wss.sbpdcl.co.in/cportal/#/guest/secure/searchbill",
            timeout=60000,
        )
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)

        # Get all input details
        inputs = page.query_selector_all("input")
        print(f"All inputs found: {len(inputs)}")
        for i, inp in enumerate(inputs):
            placeholder = inp.get_attribute("placeholder")
            id_attr = inp.get_attribute("id")
            type_attr = inp.get_attribute("type")
            print(f"Input {i}: id={id_attr}, placeholder={placeholder}, type={type_attr}")

        # Try to fill using CSS selector
        try:
            ca_input = page.locator("input#mat-input-0")
            ca_input.fill("1234567890")
            print("Successfully filled input using ID selector")

            # Click search button
            search_btn = page.locator('button:has-text("Search")')
            search_btn.click()
            print("Clicked Search button")

            time.sleep(4)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Screenshot result
            page.screenshot(path="screenshots/after_search.png")

            # Get page text
            body_text = page.inner_text("body")
            print("Result page text (first 2000 chars):")
            print(body_text[:2000])

        except Exception as e:
            print(f"Error: {e}")

        browser.close()


if __name__ == "__main__":
    main()
