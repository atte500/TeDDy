from typing import Protocol


class WebScraper(Protocol):
    """
    An outbound port for fetching content from a web URL.
    """

    def get_content(self, url: str) -> str:
        """
        Fetches the content from the given URL.

        Args:
            url: The URL to fetch content from.

        Returns:
            The content of the page as a string.

        Raises:
            Any exception related to network errors or HTTP status codes.
        """
        ...
