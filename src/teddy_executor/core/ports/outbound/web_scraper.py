from typing import Protocol, runtime_checkable


@runtime_checkable
class WebScraper(Protocol):
    """
    An outbound port for fetching content from a web URL.
    """

    def get_content(self, url: str, truncate: bool = True, **_kwargs) -> str:
        """
        Fetches the content from the given URL.

        Args:
            url: The URL to fetch content from.
            truncate: Whether to apply the read.max_lines cap (default True).
                Context assembly passes False so embedded content is verbatim.
            **_kwargs: Optional extraction hints (e.g., include_comments=True).

        Returns:
            The content of the page as a string.

        Raises:
            Any exception related to network errors or HTTP status codes.
        """
        ...
