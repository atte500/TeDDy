"""Doubles for the ``litellm`` module seam.

``LiteLLMAdapter`` reaches the library through its ``_litellm_provider``
constructor parameter, so tests inject one of these instead of patching the
global ``litellm`` module, which the architecture rules forbid.
"""

from typing import Any, Dict, List, Optional


class FakeLitellmProvider:
    """A minimal, scripted stand-in for the ``litellm`` module.

    It answers the two calls preflight makes and records every completion so a
    test can prove no request was issued. Reaching ``completion`` is always a
    defect in the code under test, so it fails loudly rather than returning a
    plausible response.
    """

    class AuthenticationError(Exception):
        """Mirrors the library's auth-error type for ``_is_auth_error``."""

    def __init__(self, missing_keys: Optional[List[str]] = None) -> None:
        self._missing_keys = list(missing_keys or [])
        self.completion_calls: List[Dict[str, Any]] = []

    def validate_environment(self, model: str) -> Dict[str, Any]:
        return {"missing_keys": list(self._missing_keys)}

    def get_llm_provider(self, model: str) -> Any:
        return ("openai", model, None, None)

    def completion(self, **kwargs: Any) -> Any:
        self.completion_calls.append(kwargs)
        raise AssertionError(
            "FakeLitellmProvider.completion must not be called: the "
            "configuration was rejected before any request was issued."
        )
