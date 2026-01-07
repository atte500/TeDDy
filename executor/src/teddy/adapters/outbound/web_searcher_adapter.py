from typing import List
from ddgs import DDGS
from teddy.core.domain.models import (
    SERPReport,
    QueryResult,
    SearchResult,
    WebSearchError,
)
from teddy.core.ports.outbound.web_searcher import IWebSearcher


class WebSearcherAdapter(IWebSearcher):
    """
    An adapter that uses the ddgs library to perform web searches.
    """

    def search(self, queries: List[str]) -> SERPReport:
        """
        Performs a web search for each query and maps the results.
        """
        all_query_results = []
        try:
            with DDGS() as ddgs:
                for query in queries:
                    # DDGS.text returns a generator, so we convert it to a list
                    results = list(ddgs.text(query, max_results=5))

                    search_results_for_query = [
                        SearchResult(
                            title=res.get("title", ""),
                            url=res.get("href", ""),
                            snippet=res.get("body", ""),
                        )
                        for res in results
                    ]

                    all_query_results.append(
                        QueryResult(
                            query=query, search_results=search_results_for_query
                        )
                    )
            return SERPReport(results=all_query_results)
        except Exception as e:
            raise WebSearchError(f"Failed to execute search: {e}") from e
