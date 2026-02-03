from unittest.mock import patch, MagicMock
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter
from teddy_executor.core.domain.models import SERPReport, WebSearchError
import pytest


def test_search_success_maps_results_correctly():
    """
    Tests that the adapter correctly calls the ddgs library and maps the
    results to the SERPReport domain object.
    """
    # Arrange
    adapter = WebSearcherAdapter()
    queries = ["python", "teddy"]

    # This is the raw result from the ddgs library
    mock_ddgs_result = [
        {
            "title": "Welcome to Python.org",
            "href": "https://www.python.org/",
            "body": "The official home of the Python Programming Language",
        }
    ]

    # Patch DDGS where it's used: in the web_searcher_adapter module
    with patch(
        "teddy_executor.adapters.outbound.web_searcher_adapter.DDGS"
    ) as mock_ddgs_class:
        # Configure the instance and its text method
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = mock_ddgs_result
        # The __enter__ method of the class's return value should return the instance
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs_instance

        # Act
        report = adapter.search(queries)

        # Assert
        assert isinstance(report, SERPReport)
        assert len(report.results) == 2
        assert report.results[0].query == "python"
        assert len(report.results[0].search_results) == 1

        search_result = report.results[0].search_results[0]
        assert search_result.title == "Welcome to Python.org"
        assert search_result.url == "https://www.python.org/"
        assert (
            search_result.snippet
            == "The official home of the Python Programming Language"
        )

        # Check that the mock was called for each query
        assert mock_ddgs_instance.text.call_count == 2
        mock_ddgs_instance.text.assert_any_call("python", max_results=5)


def test_search_handles_library_exception():
    """
    Tests that the adapter catches an exception from the ddgs library
    and raises a WebSearchError.
    """
    # Arrange
    adapter = WebSearcherAdapter()
    queries = ["test query"]

    # Patch DDGS where it's used: in the web_searcher_adapter module
    with patch(
        "teddy_executor.adapters.outbound.web_searcher_adapter.DDGS"
    ) as mock_ddgs_class:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = ConnectionError("Network failed")
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs_instance

        # Act & Assert
        with pytest.raises(WebSearchError, match="Failed to execute search"):
            adapter.search(queries)
