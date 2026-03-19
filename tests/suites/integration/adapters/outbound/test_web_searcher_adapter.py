from unittest.mock import patch, MagicMock
import pytest
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import IWebSearcher
from teddy_executor.core.domain.models import WebSearchError


def test_search_success_returns_websearchresults_dict(monkeypatch):
    """
    Tests that the adapter returns a dictionary conforming to the
    WebSearchResults TypedDict structure.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup().with_real_searcher()
    searcher = env.get_service(IWebSearcher)

    queries = ["python"]
    mock_ddgs_result = [
        {
            "title": "Welcome to Python.org",
            "href": "https://www.python.org/",
            "body": "The official home of the Python Programming Language",
        }
    ]

    with patch("ddgs.DDGS") as mock_ddgs_class:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = mock_ddgs_result
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs_instance

        # Act
        result = searcher.search(queries)

        # Assert
        assert isinstance(result, dict)
        assert len(result["query_results"]) == 1
        assert result["query_results"][0]["query"] == "python"
        assert (
            result["query_results"][0]["results"][0]["title"] == "Welcome to Python.org"
        )


def test_search_handles_library_exception(monkeypatch):
    """
    Tests that the adapter catches an exception from the ddgs library
    and raises a WebSearchError.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup().with_real_searcher()
    searcher = env.get_service(IWebSearcher)

    queries = ["test query"]

    # Patch DDGS where it's defined to intercept the lazy import
    with patch("ddgs.DDGS") as mock_ddgs_class:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = ConnectionError("Network failed")
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs_instance

        # Act & Assert
        with pytest.raises(WebSearchError, match="Failed to execute search"):
            searcher.search(queries)
