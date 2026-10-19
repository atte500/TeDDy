from teddy_executor.adapters.outbound.system_environment_inspector import (
    SystemEnvironmentInspector,
)
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)


def test_environment_inspector_contract_requires_get_git_status():
    """
    Verify that any implementation of IEnvironmentInspector must have get_git_status.
    """
    # Check that the method is defined on the concrete class itself, not just inherited
    assert "get_git_status" in SystemEnvironmentInspector.__dict__, (
        "SystemEnvironmentInspector must implement get_git_status directly."
    )


def test_environment_inspector_contract_excludes_full_git_status():
    """
    Verify that the redundant full git status method is gone from the contract.
    """
    assert not hasattr(IEnvironmentInspector, "get_full_git_status"), (
        "IEnvironmentInspector must not declare get_full_git_status."
    )
    assert "get_full_git_status" not in SystemEnvironmentInspector.__dict__, (
        "SystemEnvironmentInspector must not implement get_full_git_status."
    )
