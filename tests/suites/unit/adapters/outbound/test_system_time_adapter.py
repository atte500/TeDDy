from datetime import datetime, timezone
from teddy_executor.adapters.outbound.system_time_adapter import SystemTimeAdapter
from teddy_executor.core.ports.outbound.time_service import ITimeService


def test_system_time_adapter_implements_protocol():
    """Verifies that SystemTimeAdapter implements ITimeService."""
    adapter = SystemTimeAdapter()
    assert isinstance(adapter, ITimeService)


def test_system_time_adapter_now_returns_recent_local_time():
    """Verifies that now() returns the current local time."""
    adapter = SystemTimeAdapter()

    start = datetime.now()
    result = adapter.now()
    end = datetime.now()

    assert start <= result <= end
    # Ensure it's naive (local) as per standard datetime.now() behavior unless configured otherwise
    assert result.tzinfo is None


def test_system_time_adapter_now_utc_returns_recent_utc_time():
    """Verifies that now_utc() returns the current UTC time."""
    adapter = SystemTimeAdapter()

    start = datetime.now(timezone.utc)
    result = adapter.now_utc()
    end = datetime.now(timezone.utc)

    assert start <= result <= end
    assert result.tzinfo == timezone.utc
