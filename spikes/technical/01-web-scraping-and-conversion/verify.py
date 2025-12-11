import httpx
from markdownify import markdownify

# A reliable page designed for scraping practice
TEST_URL = "http://books.toscrape.com/"

def main():
    """
    Fetches an HTML page, converts it to Markdown, and prints the result.
    """
    try:
        print(f"Fetching content from {TEST_URL}...")
        response = httpx.get(TEST_URL)
        response.raise_for_status()  # Raise an exception for bad status codes

        html_content = response.text
        print("\n--- Original HTML ---")
        print(html_content)

        print("\n--- Converting to Markdown ---")
        markdown_content = markdownify(html_content)

        print("\n--- Converted Markdown ---")
        print(markdown_content)

        # Verification check
        if "All products" in markdown_content and "Books to Scrape" in markdown_content:
            print("\n✅ Verification successful: Key markdown elements found.")
            print("Success")
        else:
            print("\n❌ Verification failed: Markdown content is not as expected.")

    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}.")
        print(f"Error: {exc}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
