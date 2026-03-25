from typing import Optional
from teddy_executor.core.ports.outbound.environment_inspector import IEnvironmentInspector
from teddy_executor.adapters.outbound.system_environment_inspector import SystemEnvironmentInspector

def test_environment_inspector_contract_requires_get_git_status():
    """
    Verify that any implementation of IEnvironmentInspector must have get_git_status.
    """
    # Check that the method is defined on the concrete class itself, not just inherited
    assert "get_git_status" in SystemEnvironmentInspector.__dict__, (
        "SystemEnvironmentInspector must implement get_git_status directly."
    )