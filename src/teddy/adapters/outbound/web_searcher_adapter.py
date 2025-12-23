from typing import List
from teddy.core.domain.models import SERPReport
from teddy.core.ports.outbound.web_searcher import IWebSearcher


class WebSearcherAdapter(IWebSearcher):
    """
    A dormant adapter for the IWebSearcher port.
    It will be implemented in a later step.
    """

    def search(self, queries: List[str]) -> SERPReport:
        """
        Dormant implementation of the search method.
        """
        raise NotImplementedError("WebSearcherAdapter is not yet implemented.")
