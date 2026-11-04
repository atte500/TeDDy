"""Sandbox replica of LiteLLMAdapter with the BYOK upstream-cost fix.

Only `_reported_cost` differs from production: it prefers OpenRouter's BYOK
`usage.cost_details.upstream_inference_cost` (the user's real provider spend)
when it is positive, adding the OpenRouter fee if the provider also reported
one. All other behavior — hydration, retry, diagnostics, marking — is
inherited unchanged from `src/`.
"""

from __future__ import annotations

from typing import Any, Optional

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


class FixedLiteLLMAdapter(LiteLLMAdapter):
    """Replica adapter proving the BYOK upstream-cost fix without touching src/."""

    def _reported_cost(self, completion_response: Any) -> Optional[float]:
        upstream = self._upstream_inference_cost(completion_response)
        if upstream is not None and upstream > 0.0:
            fee = self._hidden_reported_cost(completion_response)
            return upstream + (fee if fee else 0.0)
        return self._hidden_reported_cost(completion_response)

    def _upstream_inference_cost(
        self, completion_response: Any
    ) -> Optional[float]:
        """Returns OpenRouter's BYOK upstream spend, or None when absent/non-positive.

        OpenRouter documents `usage.cost_details.upstream_inference_cost` as the
        actual cost charged by the user's own provider under BYOK, and reports
        `0` or `null` for non-BYOK requests. A zero is treated as absent so the
        reported fee remains authoritative for normal OpenRouter requests.
        """
        usage = getattr(completion_response, "usage", None)
        if usage is None:
            return None
        details = getattr(usage, "cost_details", None)
        if details is None:
            return None
        raw = (
            details.get("upstream_inference_cost")
            if isinstance(details, dict)
            else getattr(details, "upstream_inference_cost", None)
        )
        return self._finite_cost(raw)

    def _hidden_reported_cost(
        self, completion_response: Any
    ) -> Optional[float]:
        """Verbatim copy of the production `_reported_cost` hidden-params read."""
        hidden = getattr(completion_response, "_hidden_params", None)
        if not isinstance(hidden, dict):
            return None

        direct = self._finite_cost(hidden.get("response_cost"))
        if direct is not None:
            return direct

        additional_headers = hidden.get("additional_headers")
        if isinstance(additional_headers, dict):
            header_cost = self._finite_cost(
                additional_headers.get("llm_provider-x-litellm-response-cost")
            )
            if header_cost is not None:
                return header_cost

        return None
