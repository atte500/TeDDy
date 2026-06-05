"""Unit tests for the IGetContextUseCase Protocol contract."""

import inspect
from typing import Optional

from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase


class TestGetContextUseCaseContract:
    """Validates the IGetContextUseCase contract."""

    def test_get_context_accepts_cache_dir_parameter(self):
        """
        The get_context method MUST accept an optional cache_dir parameter
        to support session-level web content caching. This test inspects
        the Protocol's signature to verify the parameter exists.
        """
        sig = inspect.signature(IGetContextUseCase.get_context)
        params = sig.parameters

        assert "cache_dir" in params, (
            "IGetContextUseCase.get_context must have a 'cache_dir' parameter"
        )

        cache_dir_param = params["cache_dir"]
        assert cache_dir_param.default is None, (
            "cache_dir must default to None for backward compatibility"
        )
        assert cache_dir_param.annotation == Optional[str], (
            f"cache_dir must be annotated as Optional[str], "
            f"got {cache_dir_param.annotation}"
        )

    def test_cache_dir_defaults_to_none(self):
        """
        The cache_dir parameter MUST default to None to preserve backward
        compatibility for callers that don't provide it (PlanningService,
        session_cli_handlers).
        """
        sig = inspect.signature(IGetContextUseCase.get_context)
        cache_dir_param = sig.parameters.get("cache_dir")

        assert cache_dir_param is not None, "cache_dir parameter must exist"
        assert cache_dir_param.default is None, (
            f"cache_dir default must be None, got {cache_dir_param.default}"
        )
