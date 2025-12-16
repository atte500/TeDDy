# Outbound Adapter: Web Scraper Adapter

**Motivating Slice:** [Slice 04: Implement `read` Action](../../slices/04-read-action.md)

## 1. Purpose

The `WebScraperAdapter` is the concrete implementation of the `WebScraper` outbound port. Its responsibility is to handle the technical details of fetching content from a URL and converting it from HTML to a clean Markdown format for use by the core application.

## 2. Implemented Ports

*   [`WebScraper`](../../core/ports/outbound/web_scraper.md)

## 3. Implementation Notes

*   **HTTP Client:** The `requests` library is used for its simplicity and widespread adoption for synchronous HTTP requests.
*   **Error Handling:** The adapter calls `response.raise_for_status()` to automatically raise an `HTTPError` for non-2xx responses, which is then caught by the `PlanService`.
*   **HTML Conversion:** The `markdownify` library is used to convert the fetched HTML content into clean Markdown.
*   **User Agent:** A default browser-like `User-Agent` header is sent with requests to avoid being blocked by simple anti-bot measures.

## 4. Key Code Snippet

The following snippet demonstrates the core logic for fetching and converting content.

```python
import requests
from markdownify import markdownify

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"

class WebScraperAdapter(WebScraper):
    def get_content(self, url: str) -> str:
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        html_content = response.text
        markdown_content = markdownify(html_content)
        return markdown_content
```

## 5. External Documentation

*   [`requests` Official Documentation](https://requests.readthedocs.io/en/latest/)
*   [`markdownify` on PyPI](https://pypi.org/project/markdownify/)
