from typing import get_type_hints
from teddy_executor.core.domain.models.web_search_results import (
    SearchResult,
    QueryResult,
    WebSearchResults,
)


def test_search_result_contract_does_not_contain_content():
    """
    Asserts that 'content' is no longer part of the SearchResult TypedDict.
    This ensures we are reverting the deep search behavior at the contract level.
    """
    hints = get_type_hints(SearchResult)
    assert "content" not in hints, (
        "SearchResult should no longer contain a 'content' field."
    )


def test_search_result_structure():
    """Verify the structure of SearchResult with core fields."""
    result: SearchResult = {
        "title": "Title",
        "href": "https://example.com",
        "body": "Snippet",
    }
    assert result["title"] == "Title"
    assert result["href"] == "https://example.com"
    assert result["body"] == "Snippet"


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
