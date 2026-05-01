import logging
from typing import List
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
        from ddgs import DDGS
        from ddgs.base import BaseSearchEngine

        # Monkeypatch BaseSearchEngine.extract_results to prevent word mashing.
        # The library joins extracted text nodes with an empty string, mashing words
        # previously separated by HTML tags (e.g. <b>). We fix this by joining with a space.
        def patched_extract_results(self, html_text: str):
            html_text = self.pre_process_html(html_text)
            tree = self.extract_tree(html_text)
            items = tree.xpath(self.items_xpath)
            results = []
            for item in items:
                result = self.result_type()
                for key, value in self.elements_xpath.items():
                    parts = (x.strip() for x in item.xpath(value))
                    # JOIN WITH SPACE instead of empty string to preserve boundaries
                    data = " ".join(" ".join(parts).split())
                    result.__setattr__(key, data)
                results.append(result)
            return results

        # Apply the structural patch to the base class
        BaseSearchEngine.extract_results = patched_extract_results  # type: ignore[method-assign]

        all_query_results: List[QueryResult] = []
        import re

        def clean_snippet(text: str) -> str:
            """Fixes missing spaces after punctuation in raw text."""
            if not text:
                return ""
            # Fix missing space after period, comma, or colon followed by a letter
            return re.sub(r"([.,:])([A-Za-z])", r"\1 \2", text)

        try:
            # Globally disable logging (CRITICAL and below) to silence noisy
            # third-party HTTP clients (urllib3, httpx, curl_cffi) used by DDGS.
            logging.disable(logging.CRITICAL)
            try:
                with DDGS() as ddgs_client:
                    for query in queries:
                        # DDGS.text returns a generator, so we convert it to a list
                        results = list(ddgs_client.text(query, max_results=5))

                        search_results_for_query: List[SearchResult] = [
                            {
                                "title": res.get("title", ""),
                                "href": res.get("href", ""),
                                "body": clean_snippet(res.get("body", "")),
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
