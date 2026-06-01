from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter


def test_search_handles_partial_query_failures():
    """
    Verify that if one query fails in a multi-query search, the adapter
    returns an empty result set for that query but still succeeds for others.
    """
    # Arrange
    mock_instance = POSIXPathMock()

    def side_effect(query, max_results=5):
        _ = max_results  # Use variable to satisfy Vulture
        if "fail" in query:
            raise Exception("No results found")
        return [
            {
                "title": f"Result for {query}",
                "href": "http://example.com",
                "body": "Snippet",
            }
        ]

    mock_instance.text.side_effect = side_effect
    mock_factory = POSIXPathMock()
    mock_factory.return_value.__enter__.return_value = mock_instance

    adapter = WebSearcherAdapter(
        config_service=POSIXPathMock(), ddgs_factory=mock_factory
    )

    # Act
    results = adapter.search(["success", "fail"])

    # Assert
    assert len(results["query_results"]) == 2

    success_res = next(r for r in results["query_results"] if r["query"] == "success")
    assert len(success_res["results"]) == 1
    assert success_res["results"][0]["title"] == "Result for success"

    fail_res = next(r for r in results["query_results"] if r["query"] == "fail")
    assert len(fail_res["results"]) == 0
