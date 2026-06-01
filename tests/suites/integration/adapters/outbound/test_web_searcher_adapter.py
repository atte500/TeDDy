import pytest
from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter
from teddy_executor.core.domain.models import WebSearchError


def test_search_success_returns_websearchresults_dict(monkeypatch):
    """
    Tests that the adapter returns a dictionary conforming to the
    WebSearchResults TypedDict structure.
    """
    # Arrange
    mock_ddgs_instance = POSIXPathMock()
    mock_ddgs_instance.text.return_value = [
        {
            "title": "Welcome to Python.org",
            "href": "https://www.python.org/",
            "body": "The official home of the Python Programming Language",
        }
    ]
    mock_factory = POSIXPathMock()
    mock_factory.return_value.__enter__.return_value = mock_ddgs_instance

    # Inject the mock factory directly into the adapter
    searcher = WebSearcherAdapter(
        config_service=POSIXPathMock(), ddgs_factory=mock_factory
    )
    queries = ["python"]

    # Act
    result = searcher.search(queries)

    # Assert
    assert isinstance(result, dict)
    assert len(result["query_results"]) == 1
    assert result["query_results"][0]["query"] == "python"
    assert result["query_results"][0]["results"][0]["title"] == "Welcome to Python.org"


def test_search_cleans_snippet_spacing(monkeypatch):
    """
    Tests that the adapter cleans missing spaces after punctuation
    and preserves boundaries between HTML tags via structural patch.
    """
    # Arrange
    mock_ddgs_instance = POSIXPathMock()
    mock_ddgs_instance.text.return_value = [
        {
            "title": "Test",
            "href": "https://test.com",
            "body": "Missing space.Here.And,there:now.",
        }
    ]
    mock_factory = POSIXPathMock()
    mock_factory.return_value.__enter__.return_value = mock_ddgs_instance

    searcher = WebSearcherAdapter(
        config_service=POSIXPathMock(), ddgs_factory=mock_factory
    )
    queries = ["test"]

    # Act
    result = searcher.search(queries)

    # Assert
    cleaned_body = result["query_results"][0]["results"][0]["body"]
    assert cleaned_body == "Missing space. Here. And, there: now."


def test_search_handles_library_exception(monkeypatch):
    """
    Tests that the adapter catches an exception from the ddgs library
    and raises a WebSearchError.
    """
    # Arrange
    mock_ddgs_instance = POSIXPathMock()
    mock_ddgs_instance.text.side_effect = ConnectionError("Network failed")
    mock_factory = POSIXPathMock()
    mock_factory.return_value.__enter__.return_value = mock_ddgs_instance

    searcher = WebSearcherAdapter(
        config_service=POSIXPathMock(), ddgs_factory=mock_factory
    )
    queries = ["test query"]

    # Act & Assert
    with pytest.raises(WebSearchError, match="Failed to execute search"):
        searcher.search(queries)


def test_search_performs_deep_scraping_for_results():
    """
    Verify that the searcher uses the provided scraper to fetch full
    content for each search result.
    """
    # Arrange
    mock_ddgs_instance = POSIXPathMock()
    mock_ddgs_instance.text.return_value = [
        {
            "title": "Python",
            "href": "https://python.org",
            "body": "Snippet",
        }
    ]
    mock_factory = POSIXPathMock()
    mock_factory.return_value.__enter__.return_value = mock_ddgs_instance

    mock_scraper = POSIXPathMock()
    mock_scraper.get_content.return_value = "Full scraped content"

    # Act
    # Inject dependencies
    searcher = WebSearcherAdapter(
        config_service=POSIXPathMock(),
        ddgs_factory=mock_factory,
        scraper=mock_scraper,
    )
    result = searcher.search(["python"])

    # Assert
    assert result["query_results"][0]["results"][0]["content"] == "Full scraped content"
    mock_scraper.get_content.assert_called_once_with("https://python.org")


def test_search_returns_untruncated_content_from_scraper():
    """
    Ensures that WebSearcherAdapter returns the exact content provided by the scraper,
    delegating truncation responsibility entirely to the WebScraperAdapter.
    """
    # Arrange
    mock_config = POSIXPathMock()
    # Default behavior for max_results
    mock_config.get_setting.return_value = 5

    mock_ddgs_instance = POSIXPathMock()
    mock_ddgs_instance.text.return_value = [{"title": "T", "href": "H", "body": "B"}]
    mock_factory = POSIXPathMock()
    mock_factory.return_value.__enter__.return_value = mock_ddgs_instance

    mock_scraper = POSIXPathMock()
    large_string = "A" * 10000
    mock_scraper.get_content.return_value = large_string

    searcher = WebSearcherAdapter(
        config_service=mock_config,
        ddgs_factory=mock_factory,
        scraper=mock_scraper,
    )

    # Act
    result = searcher.search(["query"])

    # Assert
    content = result["query_results"][0]["results"][0]["content"]
    assert content == large_string
    assert "[TRUNCATED" not in content
