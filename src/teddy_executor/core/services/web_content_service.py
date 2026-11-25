"""Coordinator owning the single cached-fetch workflow for remote content."""

from typing import Optional, Sequence

from teddy_executor.core.ports.outbound.web_content_cache import IWebContentCache
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper


class WebContentService:
    """Resolves remote resources through one session-scoped cache.

    Every surface that reads a remote resource goes through this coordinator, so
    the cache is consulted in one place and a stored body is always the fetched
    body verbatim.
    """

    def __init__(self, web_scraper: IWebScraper, cache: IWebContentCache) -> None:
        self._web_scraper = web_scraper
        self._cache = cache

    def fetch_many(
        self, urls: Sequence[str], *, session_root: Optional[str] = None
    ) -> dict[str, Optional[str]]:
        """Resolve every requested URL, caching each successful fetch.

        Args:
            urls: Absolute URLs; duplicates are resolved once.
            session_root: The session directory, or None when no session is in scope.

        Returns:
            One entry per distinct URL, mapped to its verbatim body, or None when
            that URL's fetch failed. No body is capped, because assembly embeds
            cached content verbatim.
        """
        entries = self._cache.load_entries(session_root)
        bodies: dict[str, Optional[str]] = {}
        fetched: dict[str, str] = {}
        for url in dict.fromkeys(urls):
            if url in entries:
                bodies[url] = entries[url]
                continue
            body = self._fetch_verbatim(url)
            if body is None:
                bodies[url] = None
                continue
            fetched[url] = body
            bodies[url] = body
        if fetched:
            self._cache.merge_entries(session_root, fetched)
        return bodies

    def _fetch_verbatim(self, url: str) -> Optional[str]:
        """Fetch one body verbatim, mapping a fetch failure to None.

        The scraper port raises provider-specific network errors, and one
        unreachable URL must not abort a whole payload, so a failure is data the
        caller renders rather than an error that propagates.
        """
        try:
            return self._web_scraper.get_content(url, truncate=False)
        except Exception:  # A failed URL is payload data, not control flow.
            return None
