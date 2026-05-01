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
        import ddgs.utils

        # Monkeypatch ddgs.utils._normalize_text to prevent word mashing.
        # The library strips HTML tags (used for highlighting) without adding spaces.
        def patched_normalize_text(raw: str) -> str:
            if not raw:
                return ""
            # Replace tags with space instead of empty string to preserve word boundaries
            text = ddgs.utils._REGEX_STRIP_TAGS.sub(" ", raw)
            from html import unescape
            import unicodedata

            text = unescape(text)
            text = unicodedata.normalize("NFC", text)
            c_to_none = {
                ord(ch): None for ch in set(text) if unicodedata.category(ch)[0] == "C"
            }
            if c_to_none:
                text = text.translate(c_to_none)
            return " ".join(text.split())

        # Apply patch globally for this turn
        ddgs.utils._normalize_text = patched_normalize_text

        all_query_results: List[QueryResult] = []
        import re

        def clean_snippet(text: str) -> str:
            """Fixes missing spaces after punctuation or between digits/letters."""
            if not text:
                return ""
            # Fix missing space after punctuation
            text = re.sub(r"([.,:;!?])([^\s])", r"\1 \2", text)
            # Fix missing space between digit and letter
            text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)
            text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
            return text

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
