import pytest
from unittest.mock import patch
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter


@pytest.mark.anyio
async def test_search_handles_partial_query_failures():
    """
    Verify that if one query fails in a multi-query search, the adapter
    returns an empty result set for that query but still succeeds for others.
    """
    adapter = WebSearcherAdapter()

    # We mock DDGS to simulate mixed success/failure
    with patch("ddgs.DDGS") as mock_ddgs_class:
        mock_instance = mock_ddgs_class.return_value.__enter__.return_value

        def side_effect(query, _max_results=5):
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

        # Act
        results = adapter.search(["success", "fail"])

        # Assert
        assert len(results["query_results"]) == 2

        success_res = next(
            r for r in results["query_results"] if r["query"] == "success"
        )
        assert len(success_res["results"]) == 1
        assert success_res["results"][0]["title"] == "Result for success"

        fail_res = next(r for r in results["query_results"] if r["query"] == "fail")
        assert len(fail_res["results"]) == 0
