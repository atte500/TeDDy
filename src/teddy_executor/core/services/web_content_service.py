"""Coordinator owning the single cached-fetch workflow for remote content."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Mapping, Optional, Sequence

from teddy_executor.core.domain.models.config_schema import ReadConfig
from teddy_executor.core.domain.models.exceptions import WebContentCacheError
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.web_content_cache import IWebContentCache
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper
from teddy_executor.core.utils.pdf import cap_extracted_text

logger = logging.getLogger(__name__)

# Bounds concurrent network fetches within one batch. A code constant rather
# than a configurable setting, matching the fixed pool the legacy cache path
# used; the batch never allocates more workers than it has misses.
MAX_FETCH_WORKERS = 5


class WebContentService:
    """Resolves remote resources through one session-scoped cache.

    Every surface that reads a remote resource goes through this coordinator, so
    the cache is consulted in one place and a stored body is always the fetched
    body verbatim.
    """

    def __init__(
        self,
        web_scraper: IWebScraper,
        cache: IWebContentCache,
        config_service: Optional[IConfigService] = None,
    ) -> None:
        self._web_scraper = web_scraper
        self._cache = cache
        self._config_service = config_service

    def fetch_one(
        self,
        url: str,
        *,
        session_root: Optional[str] = None,
        truncate: bool = True,
    ) -> str:
        """Resolve one URL through the session cache.

        Args:
            url: The absolute URL to resolve.
            session_root: The session directory, or None when no session is in scope.
            truncate: Whether to cap the returned body at ``read.max_lines``. A
                capped return carries the announced truncation notice, while the
                stored body is always the full fetched text.

        Returns:
            The URL's body, capped when ``truncate`` is True.

        Raises:
            The scraper's own fetch error propagates unchanged, so each surface
            keeps its existing translation.
        """
        assert url, "fetch_one requires a non-empty URL"
        entries = self._cache.load_entries(session_root)
        if url in entries:
            body = entries[url]
        else:
            body = self._web_scraper.get_content(url, truncate=False)
            self._merge_entries(session_root, {url: body})
        if not truncate:
            return body
        return cap_extracted_text(body, self._read_budget())

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
        misses: list[str] = []
        for url in dict.fromkeys(urls):
            if url in entries:
                bodies[url] = entries[url]
            else:
                misses.append(url)
        if misses:
            fetched = self._fetch_uncached(misses)
            bodies.update(fetched)
            successes = {url: body for url, body in fetched.items() if body is not None}
            if successes:
                self._merge_entries(session_root, successes)
        return bodies

    def _fetch_uncached(self, urls: Sequence[str]) -> dict[str, Optional[str]]:
        """Fetch every URL concurrently, mapping each failure to None."""
        workers = min(MAX_FETCH_WORKERS, len(urls))
        bodies: dict[str, Optional[str]] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._fetch_verbatim, url): url for url in urls}
            for future in as_completed(futures):
                bodies[futures[future]] = future.result()
        return bodies

    def _read_budget(self) -> int:
        """Resolve the read budget, falling back to the schema default."""
        if self._config_service is None:
            return ReadConfig.max_lines
        budget = self._config_service.get_setting(
            "read.max_lines", ReadConfig.max_lines
        )
        return budget if isinstance(budget, int) else ReadConfig.max_lines

    def _merge_entries(
        self, session_root: Optional[str], entries: Mapping[str, str]
    ) -> None:
        """Persist fetched bodies, tolerating a cache write failure.

        Losing a completed fetch to a cache write failure is the worse outcome,
        so the failure is logged and the fetched body is still handed back.
        """
        try:
            self._cache.merge_entries(session_root, entries)
        except WebContentCacheError as exc:
            logger.warning(
                "Could not persist the session content cache for %s: %s",
                session_root,
                exc,
            )

    def _fetch_verbatim(self, url: str) -> Optional[str]:
        """Fetch one body verbatim, mapping a fetch failure to None.

        The scraper port documents that it raises on network and HTTP failures,
        so that raise surface is expected rather than a defect. One unreachable
        URL must not abort a whole payload: the failure is logged with its
        traceback and rendered as missing data by the caller.
        """
        try:
            return self._web_scraper.get_content(url, truncate=False)
        except Exception:  # Documented raise surface of the scraper port.
            logger.warning(
                "Fetching %s failed; rendering it as missing.", url, exc_info=True
            )
            return None
