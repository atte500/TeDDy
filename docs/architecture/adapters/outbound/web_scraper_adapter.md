# Outbound Adapter: Web Scraper Adapter

**Status:** Implemented

## 1. Purpose

The `WebScraperAdapter` is the concrete implementation of the `WebScraper` outbound port. Its responsibility is to handle the technical details of fetching content from a URL and converting it from HTML to a clean Markdown format for use by the core application.

## 2. Implemented Ports

*   [`WebScraper`](../../core/ports/outbound/web_scraper.md)

## 3. Implementation Details / Logic
The adapter employs a "smart router" pattern to choose the best scraping strategy based on the URL. This hybrid approach ensures both high-quality content extraction from general web pages and perfect fidelity for source code files from GitHub.

1.  **GitHub URL Detection:** The adapter first inspects the URL. It identifies three specific patterns:
    -   **Raw Content URLs:** Domain `raw.githubusercontent.com`. Bypasses extraction and returns content immediately.
    -   **Blob URLs:** Pattern `github.com/.../blob/...`. Transformed to raw and returned immediately.
    -   **Conversation URLs:** Pattern `github.com/.../issues/...` or `github.com/.../pull/...`. Routed to the specialized `_extract_github_conversation` logic.
2.  **Raw Content Fetching:** URLs identified as raw are fetched directly using `requests`. The response text is returned as-is, bypassing `trafilatura` to prevent accidental stripping of source code or markdown.
3.  **GitHub Conversation Extraction (Issues/PRs):** Uses a **Hybrid JSON/HTML strategy** to maximize fidelity:
    -   **JSON Pass:** Scans `<script>` tags for React hydration payloads (`data-target="react-app.embeddedData"` or `id="client-env"`). Recursively searches for the `issue` or `pullRequest` container and timeline `edges`. This provides structured Markdown and metadata (authors, timestamps).
    -   **HTML Fallback:** Scrapes `.markdown-title` for the header and `.markdown-body` / `.comment-body` blocks if JSON data is missing or fragmented.
    -   **Merging:** Returns a unified Markdown string starting with the title, followed by the description and conversation items.
4.  **General Content Extraction (for all other URLs):** For all other URLs, the adapter uses a two-stage process. It first attempts a direct fetch using the `requests` library.
4.  **403 Fallback:** If the initial `requests` fetch is blocked with a `403 Forbidden` error, the adapter automatically falls back to using `trafilatura.fetch_url`. This second method is more robust and can bypass some simple anti-scraping measures.
5.  **Content Conversion:** Once the HTML content is successfully fetched (either directly or via the fallback), `trafilatura.extract` is used to strip away boilerplate and convert the main content to Markdown.
6.  **UA & Header Rotation:** To bypass Cloudflare and other anti-scraping measures (e.g., 403 Forbidden), the adapter implements a rotation strategy:
    - **User-Agent Pool:** Rotates between Chrome, Safari, and Edge on macOS/Windows.
    - **Header Hardening:** Adds `Accept-Language`, `Referer`, and `Upgrade-Insecure-Requests` to the rotation.
    - **Fingerprint Reduction:** Minimizes custom library headers that identify `requests`.

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
