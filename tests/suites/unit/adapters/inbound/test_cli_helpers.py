from teddy_executor.adapters.inbound.cli_helpers import (
    find_project_root,
    prewarm_imports,
)


def test_cli_helpers_is_importable():
    # Simple check to ensure the module can be imported and logic runs
    # This acts as our scaffolding verification.
    assert find_project_root() is not None


def test_prewarm_imports_executes_without_error():
    """Contract test: prewarm_imports() signature exists and is callable."""
    prewarm_imports()
