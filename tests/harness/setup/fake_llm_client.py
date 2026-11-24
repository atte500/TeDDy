"""In-memory fake for the ``ILlmClient`` outbound port.

Mirrors ``fake_pdf_extractor``: a small hand-written double that returns
scripted values and records every call, so wiring tests can drive the
cached-hit, zero-cache, and no-usage telemetry branches deterministically
without a spec-bound mock or a live provider.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional, Sequence

from teddy_executor.core.domain.models.token_usage import TokenUsage
from teddy_executor.core.ports.outbound.llm_client import ILlmClient

DEFAULT_COMPLETION_CONTENT = "# Mock Plan\n\n## Action Plan\n"
DEFAULT_MODEL = "fake-model"


class FakeLlmClient(ILlmClient):
    """Deterministic ``ILlmClient`` double for harness-driven tests.

    ``get_token_usage`` pops the next scripted ``TokenUsage`` and records the
    response it inspected. Once the queue drains it reports a zeroed
    ``TokenUsage``, mirroring the port default, so the no-usage branch is the
    natural resting state. Completions return a minimal, well-formed response.
    """

    def __init__(
        self,
        usages: Optional[Sequence[TokenUsage]] = None,
        completion_content: str = DEFAULT_COMPLETION_CONTENT,
    ) -> None:
        self._usages: List[TokenUsage] = list(usages or [])
        self._completion_content = completion_content
        self.usage_calls: List[Any] = []
        self.completion_calls: List[Dict[str, Any]] = []

    def enqueue_usage(self, usage: TokenUsage) -> None:
        self._usages.append(usage)

    def get_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        llm_overrides: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        self.completion_calls.append(
            {
                "messages": messages,
                "model": model,
                "llm_overrides": llm_overrides,
                "kwargs": kwargs,
            }
        )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self._completion_content),
                    finish_reason="stop",
                )
            ],
            model=DEFAULT_MODEL,
        )

    def get_token_count(
        self, messages: List[Dict[str, str]], model: Optional[str] = None
    ) -> int:
        return 0

    def get_text_token_count(self, text: str, model: Optional[str] = None) -> int:
        return 0

    def get_token_usage(self, completion_response: Any) -> TokenUsage:
        self.usage_calls.append(completion_response)
        if self._usages:
            return self._usages.pop(0)
        return TokenUsage()

    def get_completion_cost(
        self, completion_response: Any, model_override: Optional[str] = None
    ) -> float:
        return 0.0

    def validate_config(self, include_remote: bool = False) -> List[str]:
        return []

    def get_context_window(self, model: Optional[str] = None) -> int:
        return 0

    def supports_pricing(self, model: Optional[str] = None) -> bool:
        return False
