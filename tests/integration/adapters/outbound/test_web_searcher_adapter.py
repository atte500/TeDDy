from unittest.mock import patch, MagicMock
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter
from teddy_executor.core.domain.models import WebSearchError
import pytest


def test_search_success_returns_websearchresults_dict():
    """
    Tests that the adapter returns a dictionary conforming to the
    WebSearchResults TypedDict structure.
    """
    # Arrange
    adapter = WebSearcherAdapter()
    queries = ["python"]

    mock_ddgs_result = [
        {
            "title": "Welcome to Python.org",
            "href": "https://www.python.org/",
            "body": "The official home of the Python Programming Language",
        }
    ]

    with patch(
        "teddy_executor.adapters.outbound.web_searcher_adapter.DDGS"
    ) as mock_ddgs_class:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = mock_ddgs_result
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs_instance

        # Act
        result = adapter.search(queries)

        # Assert
        assert isinstance(result, dict)
        assert "query_results" in result
        assert len(result["query_results"]) == 1

        query_result = result["query_results"][0]
        assert query_result["query"] == "python"
        assert len(query_result["results"]) == 1

        search_result = query_result["results"][0]
        assert search_result["title"] == "Welcome to Python.org"
        assert search_result["href"] == "https://www.python.org/"
        assert (
            search_result["body"]
            == "The official home of the Python Programming Language"
        )


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
