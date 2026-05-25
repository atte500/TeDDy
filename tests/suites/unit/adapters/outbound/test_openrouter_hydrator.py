from typing import Any
from teddy_executor.adapters.outbound.openrouter_hydrator import (
    OpenRouterMetadataHydrator,
)


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
    assert metadata["pricing"]["prompt"] == "0.000001"


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
