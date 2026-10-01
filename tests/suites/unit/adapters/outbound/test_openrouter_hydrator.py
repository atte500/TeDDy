from pathlib import Path
from typing import Any

from teddy_executor.adapters.outbound.openrouter_hydrator import (
    OpenRouterMetadataHydrator,
)
from teddy_executor.core.ports.outbound import IConfigService
from tests.harness.setup.mocking import POSIXPathMock


def test_hydrator_resolves_exact_match(openrouter_mock: Any):
    """Should return metadata for an exact model ID match."""
    # Arrange
    hydrator = OpenRouterMetadataHydrator()
    # Redirect to mock server
    hydrator.API_URL = f"{openrouter_mock}api/v1/models"

    # Act
    metadata = hydrator.get_metadata("deepseek/deepseek-v4-flash")

    # Assert
    assert metadata is not None
    assert metadata["context_window"] == 1048576
    assert metadata["pricing"]["input_cost_per_token"] == 0.000001
    assert metadata["pricing"]["output_cost_per_token"] == 0.000002


def test_hydrator_resolves_suffix_match(openrouter_mock: Any):
    """Should strip date suffixes to find a match (e.g. -20240525)."""
    # Arrange
    hydrator = OpenRouterMetadataHydrator()
    hydrator.API_URL = f"{openrouter_mock}api/v1/models"

    # Act
    # deepseek/deepseek-v4-flash exists in mock
    metadata = hydrator.get_metadata("deepseek/deepseek-v4-flash-20260423")

    # Assert
    assert metadata is not None
    assert metadata["context_window"] == 1048576


def test_hydrator_returns_none_on_no_match(openrouter_mock: Any):
    """Should return None if model is not found even after stripping."""
    # Arrange
    hydrator = OpenRouterMetadataHydrator()
    hydrator.API_URL = f"{openrouter_mock}api/v1/models"

    # Act
    metadata = hydrator.get_metadata("non-existent/model")

    # Assert
    assert metadata is None


def test_hydrator_handles_api_failure(httpserver: Any):
    """Should handle non-200 responses gracefully."""
    # Arrange
    url = httpserver.url_for("/api/v1/models")
    httpserver.expect_request("/api/v1/models").respond_with_json({}, status=500)
    hydrator = OpenRouterMetadataHydrator()
    hydrator.API_URL = url

    # Act
    metadata = hydrator.get_metadata("deepseek/deepseek-v3")

    # Assert
    assert metadata is None


class TestConstructorInjectionSeam:
    """Seam: optional cache dependencies enter via Constructor Injection.

    Zero-arg construction must preserve the legacy behavior exactly
    (no persistent cache, no config dependency). The factory in
    registries/infrastructure.py passes the real values. The persistent
    cache BEHAVIOR is driven out by the Logic deliverable; this seam
    only establishes the injection surface.
    """

    def test_cache_path_constant_matches_spec(self):
        assert OpenRouterMetadataHydrator.CACHE_PATH == Path(
            ".teddy/.model_registry_cache.json"
        )

    def test_zero_arg_construction_defaults_cache_path_to_none(self):
        hydrator = OpenRouterMetadataHydrator()

        assert hydrator.cache_path is None

    def test_zero_arg_construction_defaults_config_service_to_none(self):
        hydrator = OpenRouterMetadataHydrator()

        assert hydrator.config_service is None

    def test_injected_cache_path_is_stored_verbatim(self):
        custom_path = Path("custom/.model_registry_cache.json")

        hydrator = OpenRouterMetadataHydrator(cache_path=custom_path)

        assert hydrator.cache_path is custom_path

    def test_injected_config_service_is_stored_verbatim(self):
        config_double: Any = POSIXPathMock(spec=IConfigService)

        hydrator = OpenRouterMetadataHydrator(config_service=config_double)

        assert hydrator.config_service is config_double


def test_hydrator_handles_string_typed_pricing(httpserver: Any):
    """Should gracefully handle non-convertible string-typed pricing values.

    Regression test for: "unsupported operand type(s) for +: 'float' and 'str'"
    crash that occurs when the OpenRouter API returns pricing values in
    unexpected formats (e.g., "$0.000001" with currency prefix) that causes
    float() to raise ValueError. The hydrator should return None gracefully
    rather than crashing.
    """
    # Arrange
    url = httpserver.url_for("/api/v1/models")
    httpserver.expect_request("/api/v1/models").respond_with_json(
        {
            "data": [
                {
                    "id": "test/model-with-currency-pricing",
                    "context_length": 64000,
                    "pricing": {
                        "prompt": "$0.000001",
                        "completion": "$0.000002",
                    },
                }
            ]
        },
        status=200,
    )
    hydrator = OpenRouterMetadataHydrator()
    hydrator.API_URL = url

    # Act
    metadata = hydrator.get_metadata("test/model-with-currency-pricing")

    # Assert
    # The hydrator should return None when pricing values cannot be converted
    # to float, preventing downstream crashes in LiteLLM's internal cost
    # calculation logic.
    assert metadata is None
