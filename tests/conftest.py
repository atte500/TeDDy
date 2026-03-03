import sys
from pathlib import Path
import pytest

# Add the project root directory to the Python path.
# This is necessary to ensure that `pytest` can correctly resolve imports
# when running tests from a specific file path, as it might not add the
# project root to `sys.path` by default in that scenario.
# We add it to the beginning of the list to ensure it's checked first.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def container(monkeypatch):
    """
    Provides a fresh DI container for each test and automatically
    patches the global container in teddy_executor.__main__.
    """
    from teddy_executor.container import create_container
    import teddy_executor.__main__

    c = create_container()
    monkeypatch.setattr(teddy_executor.__main__, "container", c)
    return c
