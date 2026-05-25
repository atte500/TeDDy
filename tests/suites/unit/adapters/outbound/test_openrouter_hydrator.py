from typing import Protocol, Optional, Dict, Any


# The contract we are about to define
class IOpenRouterHydrator(Protocol):
    def get_metadata(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches metadata for a model from OpenRouter.
        Returns a dict with 'context_window' and 'pricing' if found, else None.
        """
        ...


def test_hydrator_contract_exists():
    # This test simply asserts that the type exists and has the expected method.
    # It will fail if I cannot import it from the target location.
    from teddy_executor.adapters.outbound.litellm_adapter import IOpenRouterHydrator

    assert hasattr(IOpenRouterHydrator, "get_metadata")
