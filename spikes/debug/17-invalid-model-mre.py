"""
MRE: Invalid model name → unknown context window & cost
Reproduces the symptom where `teddy start --model openrouter/deepseek/deepseek-v4-proh:nitro`
displays ??? for context tokens and $??? for cost.

We test the core methods that the telemetry display relies on.
"""
import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.adapters.outbound.openrouter_hydrator import OpenRouterMetadataHydrator


class MockConfigService:
    """Minimal config service that returns our test model."""
    def get_setting(self, key, default=None):
        if key == "llm.model":
            return self._model
        if key == "llm":
            return {"model": self._model}
        return default

    def __init__(self, model):
        self._model = model


def test_model(model_name: str, label: str):
    """Simulate the telemetry display logic."""
    config = MockConfigService(model_name)
    hydrator = OpenRouterMetadataHydrator()
    adapter = LiteLLMAdapter(config_service=config, hydrator=hydrator)

    context_window = adapter.get_context_window(model=model_name)
    pricing_supported = adapter.supports_pricing(model=model_name)

    # Also test hydrator directly
    metadata = hydrator.get_metadata(model_name)

    print(f"=== {label} ===")
    print(f"Model: {model_name}")
    print(f"  get_context_window() = {context_window}  (0 → ???, valid → e.g. 128000)")
    print(f"  supports_pricing()   = {pricing_supported}  (False → $???)")
    print(f"  Hydrator metadata    = {metadata}")
    print()


if __name__ == "__main__":
    # 1. Invalid model (user's report)
    test_model(
        "openrouter/deepseek/deepseek-v4-proh:nitro",
        "Scenario 1: Invalid model (user's report)"
    )

    # 2. Valid existing model for comparison
    test_model(
        "openrouter/openai/gpt-4o",
        "Scenario 2: Valid model (comparison)"
    )

    # 3. Invalid model without prefix/suffix to isolate hydrator behavior
    test_model(
        "deepseek/deepseek-v4-proh:nitro",
        "Scenario 3: Invalid model without openrouter/ prefix"
    )

    # 4. The sanitized ID (after hydrator stripping) to see if it's known
    test_model(
        "deepseek/deepseek-v4-proh",
        "Scenario 4: After hydrator stripping prefix and suffix"
    )