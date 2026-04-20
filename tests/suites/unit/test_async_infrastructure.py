import pytest
import anyio


@pytest.mark.anyio
async def test_anyio_infrastructure_is_functional():
    # Verify we can run a simple async operation
    result = await anyio.to_thread.run_sync(lambda: True)
    assert result is True
