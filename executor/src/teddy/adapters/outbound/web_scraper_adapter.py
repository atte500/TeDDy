import requests
from markdownify import markdownify

from teddy.core.ports.outbound.web_scraper import WebScraper


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"


class WebScraperAdapter(WebScraper):
    """
    An adapter that implements the WebScraper port using the requests library.
    """

    def get_content(self, url: str) -> str:
        """
        Fetches the content from the given URL using an HTTP GET request.

        Args:
            url: The URL to fetch content from.

        Returns:
            The text content of the page.

        Raises:
            requests.exceptions.RequestException: For connection errors or non-200
                                                  status codes.
        """
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        html_content = response.text
        markdown_content = markdownify(html_content)
        return markdown_content
