from datetime import datetime, timezone
from teddy_executor.core.ports.outbound.time_service import ITimeService


class SystemTimeAdapter(ITimeService):
    """
    Production implementation of ITimeService using the standard library.
    """

    def now(self) -> datetime:
        """Returns current local time."""
        return datetime.now()

    def now_utc(self) -> datetime:
        """Returns current UTC time."""
        return datetime.now(timezone.utc)
