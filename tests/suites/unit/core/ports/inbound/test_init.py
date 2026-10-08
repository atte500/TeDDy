"""Unit tests for the IInitUseCase inbound port contract."""

import inspect

from teddy_executor.core.ports.inbound.init import IInitUseCase


class TestInitUseCaseContract:
    """Validates the IInitUseCase contract."""

    def test_ensure_templates_initialized_is_declared_as_abstract(self):
        """
        IInitUseCase MUST declare ensure_templates_initialized so consumers
        (CLI subcommand, auto-init) can regenerate docs/templates/ through the
        inbound port rather than reaching into the concrete service.
        """
        assert "ensure_templates_initialized" in IInitUseCase.__abstractmethods__, (
            "IInitUseCase must declare ensure_templates_initialized as an "
            "abstract member"
        )

    def test_ensure_templates_initialized_signature(self):
        """
        ensure_templates_initialized MUST accept an `overwrite` flag defaulting
        to False so the auto-init path stays non-destructive while the explicit
        `teddy init templates` command can pass overwrite=True.
        """
        sig = inspect.signature(IInitUseCase.ensure_templates_initialized)
        params = sig.parameters

        assert "overwrite" in params, (
            "ensure_templates_initialized must accept an 'overwrite' parameter"
        )
        assert params["overwrite"].default is False, (
            "overwrite must default to False so auto-init is non-destructive"
        )
