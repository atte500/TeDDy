# Outbound Adapter: Web Scraper Adapter

**Motivating Slice:** [Slice 04: Implement `read` Action](../../slices/04-read-action.md)

## 1. Purpose

The `WebScraperAdapter` is the concrete implementation of the `WebScraper` outbound port. Its responsibility is to handle the technical details of fetching content from a URL and converting it from HTML to a clean Markdown format for use by the core application.

## 2. Implemented Ports

*   [`WebScraper`](../../core/ports/outbound/web_scraper.md)

## 3. Implementation Notes

This adapter's implementation was de-risked through a technical spike.

*   **Technical Spike:** `spikes/technical/01-web-scraping-and-conversion/`
*   **HTTP Client:** The `httpx` library was chosen for its modern API, synchronous support (matching our current needs), and readiness for future asynchronous use cases. It provides robust error handling with `response.raise_for_status()`.
*   **HTML Conversion:** The `markdownify` library was selected for its simplicity and effectiveness in converting HTML to Markdown. It requires `beautifulsoup4` as a dependency.

## 4. Key Code Snippet

The following snippet from the verification spike (`verify.py`) demonstrates the core logic for fetching and converting content. The final adapter should encapsulate this logic within the `get_content` method.

```python
import httpx
from markdownify import markdownify

def get_content(url: str) -> str:
    """
    Fetches an HTML page, converts it to Markdown, and returns the result.
    """
    try:
        response = httpx.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes

        html_content = response.text
        markdown_content = markdownify(html_content)

        return markdown_content

    except httpx.RequestError as exc:
        # The adapter should catch specific exceptions and raise a
        # domain-specific exception as defined by the port contract.
        # e.g., raise WebContentError(f"Failed to fetch {url}: {exc}")
        raise RuntimeError(f"An error occurred while requesting {exc.request.url!r}: {exc}")

```

## 5. External Documentation

*   [`httpx` Official Documentation](https://www.python-httpx.org/)
*   [`markdownify` on PyPI](https://pypi.org/project/markdownify/)
