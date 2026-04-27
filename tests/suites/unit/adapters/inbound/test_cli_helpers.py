from teddy_executor.adapters.inbound.cli_helpers import find_project_root


def test_cli_helpers_is_importable():
    # Simple check to ensure the module can be imported and logic runs
    # This acts as our scaffolding verification.
    assert find_project_root() is not None
