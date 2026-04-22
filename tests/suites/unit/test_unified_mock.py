import pytest
from unittest.mock import AsyncMock
from tests.harness.setup.mocking import POSIXPathMock


class IAsyncPort:
    def method(self, path: str): ...
    async def async_method(self, path: str): ...


def test_posix_path_mock_is_not_async_aware_by_default():
    mock = POSIXPathMock(spec=IAsyncPort)
    # This currently returns a MagicMock, not an AsyncMock
    assert not isinstance(mock.async_method, AsyncMock)


@pytest.mark.anyio
async def test_unified_mock_is_async_aware():
    from tests.harness.setup.mocking import UnifiedMock

    mock = UnifiedMock(spec=IAsyncPort)

    # Should be an AsyncMock
    assert isinstance(mock.async_method, AsyncMock)

    # Should be awaitable
    mock.async_method.return_value = "done"
    assert await mock.async_method("test") == "done"

    # Should still normalize paths
    mock.async_method.assert_called_with("test")
    mock.method("C:\\test")
    mock.method.assert_called_with("C:/test")


def test_unified_mock_synchronizes_sync_and_async_return_values():
    """
    Harness: Setting return_value on a sync method MUST update its async counterpart.
    """
    from tests.harness.setup.mocking import UnifiedMock

    mock = UnifiedMock(spec=IAsyncPort)

    # 1. Set on sync
    mock.method.return_value = "synced"

    # 2. Check async (Should be synced)
    assert mock.async_method.return_value == "synced"


@pytest.mark.anyio
async def test_unified_mock_synchronizes_sync_and_async_side_effects():
    """
    Harness: Setting side_effect on a sync method MUST update its async counterpart.
    """
    from tests.harness.setup.mocking import UnifiedMock

    mock = UnifiedMock(spec=IAsyncPort)

    def effect(*args, **kwargs):
        return "effect-result"

    # 1. Set on sync
    mock.method.side_effect = effect

    # 2. Check async call
    result = await mock.async_method("test")
    assert result == "effect-result"
