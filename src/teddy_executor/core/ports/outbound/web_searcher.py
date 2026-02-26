from abc import ABC, abstractmethod
from typing import List
from teddy_executor.core.domain.models import WebSearchResults


class IWebSearcher(ABC):
    """
    Outbound port for performing web searches.
    """

    @abstractmethod
    def search(self, queries: List[str]) -> WebSearchResults:
        """
        Performs a web search for each query in the list.

        Args:
            queries: A list of search query strings.

        Returns:
            A SERPReport object containing the aggregated search results.

        Raises:
            WebSearchError: If the search operation fails for any reason.
        """
        raise NotImplementedError
