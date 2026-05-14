from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class ITimeService(Protocol):
    """
    Outbound Port for deterministic time access.
    Enables testing of time-dependent logic (e.g., session naming, timestamps).
    """

    def now(self) -> datetime:
        """
        Returns the current local date and time.
        """
        ...

    def now_utc(self) -> datetime:
        """
        Returns the current UTC date and time.
        """
        ...
