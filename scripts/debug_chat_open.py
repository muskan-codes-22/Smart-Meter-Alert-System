"""Debug WhatsApp chat opening - fixed version."""
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
    screenshot_dir = Path("screenshots")
    screenshot_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
        )

        page = context.new_page()
        page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(8)

        page.screenshot(path=str(screenshot_dir / "debug_01_initial.png"))
        print("1. Initial page loaded")

        # Find search input
        search_selectors = [
            '[placeholder="Search or start a new chat"]',
            'div[contenteditable="true"][data-tab="3"]',
            'div[aria-label="Search or start a new chat"]',
        ]

        search_input = None
        for sel in search_selectors:
            try:
                elem = page.locator(sel)
                if elem.count() > 0 and elem.first.is_visible():
                    search_input = elem.first
                    print(f"2. Found search input: {sel}")
                    break
            except Exception:
                continue

        if search_input is None:
            print("ERROR: Could not find search input")
            context.close()
            return

        # Type phone number
        search_input.click()
        time.sleep(0.5)
        page.keyboard.press("Control+a")
        page.keyboard.press("Backspace")
        time.sleep(0.3)
        search_input.type("916282905752", delay=50)
        print("3. Typed phone number")
        time.sleep(3)
        page.screenshot(path=str(screenshot_dir / "debug_02_search.png"))

        # Find all list items and inspect them
        print("4. Inspecting list items...")
        all_items = page.locator('[data-testid*="list-item"]').all()
        print(f"   Total items with list-item testid: {len(all_items)}")
        for i, item in enumerate(all_items):
            try:
                text = item.inner_text()[:50]
                tag = item.evaluate('el => el.tagName')
                print(f"     [{i}] tag={tag}, text='{text}', visible={item.is_visible()}")
            except Exception as e:
                print(f"     [{i}] Error: {e}")

        # Better approach: look for the contact row specifically
        # The contact row should have a span with the name or phone
        print("\n5. Looking for Muskan contact...")
        
        # Method 1: Look for span with title="Muskan"
        muskan_span = page.locator('span[title="Muskan"]')
        print(f"   span[title='Muskan']: count={muskan_span.count()}")
        
        if muskan_span.count() > 0:
            # Find the parent clickable element
            muskan_row = muskan_span.first.locator('xpath=ancestor::div[contains(@data-testid,"list-item")]')
            print(f"   Parent list-item: count={muskan_row.count()}")
            if muskan_row.count() > 0:
                muskan_row.first.click()
                print("   Clicked Muskan row via parent")
            else:
                muskan_span.first.click()
                print("   Clicked Muskan span directly")
        else:
            # Method 2: Look for div with role="listitem" or similar
            # Try clicking on the div that contains "Muskan"
            muskan_div = page.locator('div:has(span:text("Muskan"))')
            print(f"   div with Muskan text: count={muskan_div.count()}")
            if muskan_div.count() > 0:
                # Find the most specific clickable element
                for i in range(muskan_div.count()):
                    div = muskan_div.nth(i)
                    data_testid = div.get_attribute('data-testid')
                    if data_testid and 'list-item' in data_testid:
                        div.click()
                        print(f"   Clicked div with data-testid={data_testid}")
                        break
                else:
                    muskan_div.first.click()
                    print("   Clicked first div containing Muskan")
        
        time.sleep(3)
        page.screenshot(path=str(screenshot_dir / "debug_03_after_click.png"))

        # Check if chat opened
        chat_header = page.locator('[data-testid="conversation-header"]')
        msg_list = page.locator('[data-testid="message-list"]')
        msg_input = page.locator('div[data-testid="conversation-compose-box-input"]')
        
        print(f"\n6. After click:")
        print(f"   Chat header: {chat_header.count()}")
        print(f"   Message list: {msg_list.count()}")
        print(f"   Message input: {msg_input.count()}")
        
        if msg_input.count() > 0:
            print("\nSUCCESS! Chat opened, typing test message...")
            msg_input.first.click()
            time.sleep(0.3)
            msg_input.first.fill("Test from debug script")
            time.sleep(0.3)
            page.keyboard.press("Enter")
            time.sleep(1)
            page.screenshot(path=str(screenshot_dir / "debug_04_message_sent.png"))
            print("Message sent!")
        else:
            print("\nChat still not open. Waiting more...")
            time.sleep(5)
            page.screenshot(path=str(screenshot_dir / "debug_05_waited_more.png"))
            msg_input = page.locator('div[data-testid="conversation-compose-box-input"]')
            print(f"   After wait - Message input: {msg_input.count()}")

        context.close()


if __name__ == "__main__":
    main()
