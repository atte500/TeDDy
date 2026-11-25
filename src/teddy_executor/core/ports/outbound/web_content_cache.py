from typing import Mapping, Optional, Protocol, runtime_checkable


@runtime_checkable
class IWebContentCache(Protocol):
    """
    An outbound port for the session-scoped store of fetched remote content.
    """

    def load_entries(self, session_root: Optional[str]) -> dict[str, str]:
        """
        Reads every URL-keyed body stored for the session.

        Args:
            session_root: The session directory, or None when no session is in scope.

        Returns:
            A URL-keyed map of untruncated bodies. A missing, unparseable, or
            non-string-valued cache reads as an empty map.
        """
        ...

    def merge_entries(
        self, session_root: Optional[str], entries: Mapping[str, str]
    ) -> None:
        """
        Merges the supplied bodies into the session map without dropping siblings.

        Args:
            session_root: The session directory, or None when no session is in scope.
            entries: Successfully fetched bodies, every value untruncated.

        Raises:
            WebContentCacheError: The merge could not be persisted.
        """
        ...
