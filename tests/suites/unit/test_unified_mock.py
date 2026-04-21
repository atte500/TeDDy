import pytest
from unittest.mock import AsyncMock
from tests.harness.setup.test_environment import POSIXPathMock


class IAsyncPort:
    def sync_method(self, path: str): ...
    async def async_method(self, path: str): ...


def test_posix_path_mock_is_not_async_aware_by_default():
    mock = POSIXPathMock(spec=IAsyncPort)
    # This currently returns a MagicMock, not an AsyncMock
    assert not isinstance(mock.async_method, AsyncMock)


@pytest.mark.anyio
async def test_unified_mock_is_async_aware():
    from tests.harness.setup.test_environment import UnifiedMock

    mock = UnifiedMock(spec=IAsyncPort)

    # Should be an AsyncMock
    assert isinstance(mock.async_method, AsyncMock)

    # Should be awaitable
    mock.async_method.return_value = "done"
    assert await mock.async_method("test") == "done"

    # Should still normalize paths
    mock.async_method.assert_called_with("test")
    mock.sync_method("C:\\test")
    mock.sync_method.assert_called_with("C:/test")
