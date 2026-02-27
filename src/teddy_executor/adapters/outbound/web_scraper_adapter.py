from http import HTTPStatus

import requests
import trafilatura

from teddy_executor.core.ports.outbound.web_scraper import WebScraper


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"


class WebScraperAdapter(WebScraper):
    """
    An adapter that implements the WebScraper port using requests and trafilatura.
    """

    def get_content(self, url: str) -> str:
        """
        Fetches the content from the given URL.

        - For GitHub blob URLs, it fetches the raw file content.
        - For other URLs, it uses trafilatura to extract the main content.

        Args:
            url: The URL to fetch content from.

        Returns:
            The text content of the page.

        Raises:
            requests.exceptions.RequestException: For connection errors or non-200
                                                  status codes.
        """
        headers = {"User-Agent": DEFAULT_USER_AGENT}

        if url.startswith("https://github.com/") and "/blob/" in url:
            raw_url = url.replace("github.com", "raw.githubusercontent.com").replace(
                "/blob/", "/"
            )
            response = requests.get(raw_url, headers=headers)
            response.raise_for_status()
            return response.text

        html_content = None
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text
        except requests.exceptions.HTTPError as e:
            if (
                e.response is not None
                and e.response.status_code == HTTPStatus.FORBIDDEN
            ):
                # Fallback for 403 Forbidden errors
                html_content = trafilatura.fetch_url(url)
            else:
                raise

        if not html_content:
            return ""

        markdown_content = trafilatura.extract(
            html_content,
            output_format="markdown",
            include_links=True,
            include_formatting=True,
            favor_recall=True,
            include_comments=True,
            include_tables=True,
        )

        return markdown_content if markdown_content else ""
