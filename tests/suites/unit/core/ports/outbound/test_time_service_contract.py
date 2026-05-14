from datetime import datetime
from typing import Protocol, runtime_checkable

# Note: We expect this import to fail in the Red phase
from teddy_executor.core.ports.outbound.time_service import ITimeService


def test_time_service_contract_definition():
    """Verifies that ITimeService is a runtime checkable Protocol with required methods."""
    assert issubclass(ITimeService, Protocol)
    assert runtime_checkable(ITimeService)

    # Verify method signatures via inspection (or just existence for now)
    assert hasattr(ITimeService, "now")
    assert hasattr(ITimeService, "now_utc")


def test_time_service_mock_compatibility():
    """Verifies that a mock can satisfy the ITimeService protocol."""
    from unittest.mock import create_autospec

    mock_time = create_autospec(ITimeService)

    # This just ensures we can call the methods on the mock
    mock_time.now.return_value = datetime(2026, 1, 1)
    mock_time.now_utc.return_value = datetime(2026, 1, 1)

    assert isinstance(mock_time.now(), datetime)
    assert isinstance(mock_time.now_utc(), datetime)
