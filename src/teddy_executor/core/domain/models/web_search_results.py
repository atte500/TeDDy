"""
This module defines the strictly-typed data transfer object for web search results.
"""

from typing import List, TypedDict


class SearchResult(TypedDict):
    """Represents a single search result item."""

    title: str
    href: str
    body: str


class QueryResult(TypedDict):
    """Represents the results for a single search query."""

    query: str
    results: List[SearchResult]


class WebSearchResults(TypedDict):
    """Represents the aggregated results from one or more web search queries."""

    query_results: List[QueryResult]
