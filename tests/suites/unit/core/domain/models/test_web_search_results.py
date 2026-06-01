from teddy_executor.core.domain.models.web_search_results import (
    SearchResult,
    QueryResult,
    WebSearchResults,
)


def test_search_result_structure():
    """Verify the structure of SearchResult with content."""
    result: SearchResult = {
        "title": "Title",
        "href": "https://example.com",
        "body": "Snippet",
        "content": "Full Scraped Content",
    }
    assert result["title"] == "Title"
    assert result["href"] == "https://example.com"
    assert result["body"] == "Snippet"
    assert result["content"] == "Full Scraped Content"


def test_search_result_content_is_optional():
    """Verify that content is not required in SearchResult."""
    # This should be valid according to the type hint
    result: SearchResult = {
        "title": "Title",
        "href": "https://example.com",
        "body": "Snippet",
    }
    assert "content" not in result


def test_query_result_structure():
    """Verify QueryResult contains a list of SearchResults."""
    result: SearchResult = {
        "title": "T",
        "href": "H",
        "body": "B",
    }
    query_res: QueryResult = {"query": "test", "results": [result]}
    assert query_res["query"] == "test"
    assert len(query_res["results"]) == 1


def test_web_search_results_nesting():
    """Verify WebSearchResults nests QueryResults."""
    query_res: QueryResult = {"query": "test", "results": []}
    search_results: WebSearchResults = {"query_results": [query_res]}
    assert len(search_results["query_results"]) == 1
