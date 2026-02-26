import logging
from typing import List
from ddgs import DDGS
from teddy_executor.core.domain.models import (
    QueryResult,
    SearchResult,
    WebSearchError,
    WebSearchResults,
)
from teddy_executor.core.ports.outbound.web_searcher import IWebSearcher


class WebSearcherAdapter(IWebSearcher):
    """
    An adapter that uses the ddgs library to perform web searches.
    """

    def search(self, queries: List[str]) -> WebSearchResults:
        """
        Performs a web search for each query and maps the results.
        """
        all_query_results: List[QueryResult] = []
        try:
            # Globally disable logging (CRITICAL and below) to silence noisy
            # third-party HTTP clients (urllib3, httpx, curl_cffi) used by DDGS.
            logging.disable(logging.CRITICAL)
            try:
                with DDGS() as ddgs:
                    for query in queries:
                        # DDGS.text returns a generator, so we convert it to a list
                        results = list(ddgs.text(query, max_results=5))

                        search_results_for_query: List[SearchResult] = [
                            {
                                "title": res.get("title", ""),
                                "href": res.get("href", ""),
                                "body": res.get("body", ""),
                            }
                            for res in results
                        ]

                        all_query_results.append(
                            {
                                "query": query,
                                "results": search_results_for_query,
                            }
                        )
                return {"query_results": all_query_results}
            finally:
                logging.disable(logging.NOTSET)
        except Exception as e:
            raise WebSearchError(f"Failed to execute search: {e}") from e
