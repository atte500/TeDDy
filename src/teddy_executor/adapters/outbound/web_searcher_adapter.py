import logging
from typing import Any, Callable, List, Optional
from teddy_executor.core.domain.models import (
    QueryResult,
    SearchResult,
    WebSearchError,
    WebSearchResults,
)
from teddy_executor.core.ports.outbound import IConfigService, IWebScraper, IWebSearcher


logger = logging.getLogger(__name__)


class WebSearcherAdapter(IWebSearcher):
    """
    An adapter that uses the ddgs library to perform web searches.
    """

    def __init__(
        self,
        config_service: IConfigService,
        ddgs_factory: Optional[Callable[..., Any]] = None,
        scraper: Optional[IWebScraper] = None,
    ):
        self._config_service = config_service
        self._ddgs_factory = ddgs_factory
        self._scraper = scraper

    def _apply_ddgs_monkeypatch(self) -> None:
        """Applies a structural patch to DDGS to preserve word boundaries."""
        from ddgs.base import BaseSearchEngine

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

    def _clean_snippet(self, text: str) -> str:
        """Fixes missing spaces after punctuation in raw text."""
        import re

        if not text:
            return ""
        # Fix missing space after period, comma, or colon followed by a letter
        return re.sub(r"([.,:])([A-Za-z])", r"\1 \2", text)

    def _execute_single_query(
        self, ddgs_client: Any, query: str, total_queries: int
    ) -> QueryResult:
        """Executes a single search query and maps results."""
        try:
            max_results = self._config_service.get_setting("research.max_results", 5)
            # DDGS.text returns a generator, so we convert it to a list
            results = list(ddgs_client.text(query, max_results=max_results))

            search_results_for_query: List[SearchResult] = []
            for res in results:
                url = res.get("href", "")
                item: SearchResult = {
                    "title": res.get("title", ""),
                    "href": url,
                    "body": self._clean_snippet(res.get("body", "")),
                }

                if self._scraper and url:
                    try:
                        content = self._scraper.get_content(url)
                        if content is not None:
                            # Set content immediately to avoid KeyError if truncation fails
                            item["content"] = content

                            max_val = self._config_service.get_setting(
                                "research.max_content_length", 5000
                            )
                            # Robustly detect concrete integers to avoid Mock comparison issues
                            if type(max_val) is int:
                                if len(content) > max_val:
                                    item["content"] = (
                                        content[:max_val]
                                        + "\n\n...[TRUNCATED. Use 'curl' to file or 'READ' for full depth]"
                                    )
                    except Exception as e:
                        # Log failure but continue; we still have the snippet.
                        logger.warning(f"Failed to scrape content for {url}: {e}")

                search_results_for_query.append(item)

            return {
                "query": query,
                "results": search_results_for_query,
            }
        except Exception as e:
            # Log the individual query failure but continue with other queries.
            # This prevents one failing query from sabotaging the entire action.
            logger.warning(f"Search query '{query}' failed: {e}")

            # If this is the ONLY query, we still want to raise the error
            # to maintain failure transparency (Stop the Line).
            if total_queries == 1:
                raise WebSearchError(f"Failed to execute search: {e}") from e

            return {
                "query": query,
                "results": [],
            }

    def search(self, queries: List[str]) -> WebSearchResults:
        """
        Performs a web search for each query and maps the results.
        """
        from ddgs import DDGS

        self._apply_ddgs_monkeypatch()
        all_query_results: List[QueryResult] = []
        factory = self._ddgs_factory or DDGS

        # Globally disable logging (CRITICAL and below) to silence noisy
        # third-party HTTP clients (urllib3, httpx, curl_cffi) used by DDGS.
        logging.disable(logging.CRITICAL)
        try:
            with factory() as ddgs_client:
                for query in queries:
                    result = self._execute_single_query(
                        ddgs_client, query, len(queries)
                    )
                    all_query_results.append(result)

            return {"query_results": all_query_results}
        finally:
            logging.disable(logging.NOTSET)
