# Outbound Adapter: Web Scraper Adapter

**Status:** Implemented
**Motivating Slice:** [Slice 04: Implement `read` Action](../../slices/04-read-action.md)

## 1. Purpose

The `WebScraperAdapter` is the concrete implementation of the `WebScraper` outbound port. Its responsibility is to handle the technical details of fetching content from a URL and converting it from HTML to a clean Markdown format for use by the core application.

## 2. Implemented Ports

*   [`WebScraper`](../../core/ports/outbound/web_scraper.md)

## 3. Implementation Details / Logic
The adapter employs a "smart router" pattern to choose the best scraping strategy based on the URL. This hybrid approach ensures both high-quality content extraction from general web pages and perfect fidelity for source code files from GitHub.

1.  **GitHub URL Detection:** The adapter first inspects the URL. If it matches the pattern for a GitHub file view (e.g., `github.com/.../blob/...`), it bypasses the general-purpose extraction logic.
2.  **Raw Content Fetching (for GitHub):** The GitHub URL is transformed into its corresponding "raw" content URL (e.g., `raw.githubusercontent.com/...`). The adapter then fetches this URL directly using `requests` and returns the raw file content. This was validated by the `spike_github_raw_scraper.py` spike.
3.  **General Content Extraction (for all other URLs):** For all other URLs, the adapter uses a two-stage process. It first attempts a direct fetch using the `requests` library.
4.  **403 Fallback:** If the initial `requests` fetch is blocked with a `403 Forbidden` error, the adapter automatically falls back to using `trafilatura.fetch_url`. This second method is more robust and can bypass some simple anti-scraping measures.
5.  **Content Conversion:** Once the HTML content is successfully fetched (either directly or via the fallback), `trafilatura.extract` is used to strip away boilerplate and convert the main content to Markdown.
6.  **User Agent:** A default browser-like `User-Agent` header is sent with all initial `requests` calls to avoid being blocked by simple anti-bot measures.

## 4. Data Contracts / Methods
The adapter implements the `get_content` method as defined by the `IWebScraper` port.

The following snippet demonstrates the core fallback logic.

```python
import requests
import trafilatura

class WebScraperAdapter(WebScraper):
    def get_content(self, url: str) -> str:
        # ... GitHub handling logic ...

        html_content = None
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                # Fallback for 403 Forbidden errors
                html_content = trafilatura.fetch_url(url)
            else:
                raise

        if not html_content:
            return ""

        markdown_content = trafilatura.extract(
            html_content,
            output_format="markdown",
            # ... other trafilatura options ...
        )
        return markdown_content if markdown_content else ""
```

## 5. External Documentation

*   [`requests` Official Documentation](https://requests.readthedocs.io/en/latest/)
*   [`trafilatura` Official Documentation](https://trafilatura.readthedocs.io/en/latest/)
