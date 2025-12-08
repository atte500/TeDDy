import sys
from playwright.sync_api import sync_playwright


def verify_playwright_scrape(query: str, num_results: int = 5):
    """
    Uses Playwright to scrape Google search results.
    """
    print("Starting Playwright verification spike...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
        except Exception as e:
            print(
                f"ERROR: Failed to launch browser. You may need to run 'playwright install'. Error: {e}"
            )
            sys.exit(1)

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            print(f"Navigating to Google and searching for '{query}'...")
            page.goto("https://www.google.com")

            # Handle consent dialog, which may be in English or German
            print("Checking for cookie consent dialog...")
            consent_button_en = page.get_by_role("button", name="Accept all")
            consent_button_de = page.get_by_role("button", name="Alle akzeptieren")

            if consent_button_de.is_visible(timeout=2000):
                print("German consent dialog found, clicking 'Alle akzeptieren'.")
                consent_button_de.click()
            elif consent_button_en.is_visible(timeout=2000):
                print("English consent dialog found, clicking 'Accept all'.")
                consent_button_en.click()
            else:
                print("No cookie consent dialog found, proceeding.")

            # Perform the search
            page.locator('textarea[name="q"]').fill(query)
            page.locator('textarea[name="q"]').press("Enter")

            print("Waiting for search results...")
            page.wait_for_selector(
                "#search", timeout=10000
            )  # Wait for the main results container

            print("Saving screenshot and HTML for debugging...")
            page.screenshot(path="debug_screenshot.png")
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Debug files 'debug_screenshot.png' and 'debug_page.html' saved.")

            # Extract results
            print("Extracting results with corrected selectors...")
            result_containers = page.locator("div.MjjYud").all()

            results_found = 0
            for i, container in enumerate(result_containers):
                if results_found >= num_results:
                    break

                # Use the specific class for the title h3 to avoid strict mode violation
                title_locator = container.locator("h3.LC20lb")

                # Ensure the title exists before trying to get text or find its parent link
                if title_locator.count() == 1:
                    title = title_locator.inner_text()

                    # The link is an ancestor of the h3 title
                    link_locator = title_locator.locator("xpath=./ancestor::a")
                    url = link_locator.get_attribute("href")

                    if title and url:
                        results_found += 1
                        print(f"\nResult {results_found}:")
                        print(f"  Title: {title}")
                        print(f"  URL: {url}")

            if results_found > 0:
                print(
                    f"\nSUCCESS: Successfully retrieved {results_found} search results."
                )
            else:
                print("\nWARNING: Search completed but no results were extracted.")

            # This return was part of the old hacky replacement, removing it to ensure
            # the function completes normally.

            # This block is now handled by the logic above.
            # It is being replaced by an empty string to remove it.

        except Exception as e:
            print(f"\nERROR: An error occurred during scraping: {e}")
            page.screenshot(path="error_screenshot.png")
            print("Screenshot saved to 'error_screenshot.png' for debugging.")
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    verify_playwright_scrape("playwright python")
