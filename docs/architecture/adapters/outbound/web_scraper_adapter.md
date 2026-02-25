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
3.  **General Content Extraction (for all other URLs):** For all other URLs, the adapter uses `trafilatura` to fetch the page and extract the main article content, intelligently stripping away common boilerplate like navigation, ads, and footers. It is configured to convert the extracted content to Markdown (`output_format='markdown'`). Research and spikes confirmed that default formatting options are sufficient.
4.  **User Agent:** A default browser-like `User-Agent` header is sent with all requests to avoid being blocked by simple anti-bot measures.

## 4. Data Contracts / Methods
The adapter implements the `scrape` method as defined by the `IWebScraper` port.

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
*   [`trafilatura` Official Documentation](https://trafilatura.readthedocs.io/en/latest/)
