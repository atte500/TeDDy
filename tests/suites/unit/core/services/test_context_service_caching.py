"""
Unit tests for ContextService web content caching behavior.

Tests cover:
- _load_web_cache: corruption handling, missing file, valid cache
- _save_web_cache: atomic write, directory creation
- Cache hit/miss integration in get_context URL-fetching loop
"""

import json
from pathlib import Path
from unittest.mock import Mock

from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper


from teddy_executor.core.services.context_service import ContextService


class TestLoadWebCache:
    """Tests for ContextService._load_web_cache private method."""

    def test_load_web_cache_returns_empty_dict_for_corrupt_file(self, tmp_path):
        """
        When .web_cache.json contains invalid JSON, _load_web_cache
        should return an empty dict without raising an exception.
        """
        # Arrange: create a corrupt cache file
        cache_dir = str(tmp_path / "session")
        cache_path = Path(cache_dir) / ".web_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("this is not valid json {{{", encoding="utf-8")

        # Create ContextService with dummy ports (cache methods never call them)
        service = ContextService(
            file_system_manager=object(),
            repo_tree_generator=object(),
            environment_inspector=object(),
            llm_client=object(),
            web_scraper=object(),
        )

        # Act
        result = service._load_web_cache(cache_dir)

        # Assert
        assert result == {}

    def test_load_web_cache_returns_empty_dict_for_missing_file(self, tmp_path):
        """
        When .web_cache.json does not exist, _load_web_cache
        should return an empty dict.
        """
        # Arrange
        cache_dir = str(tmp_path / "nonexistent_session")

        service = ContextService(
            file_system_manager=object(),
            repo_tree_generator=object(),
            environment_inspector=object(),
            llm_client=object(),
            web_scraper=object(),
        )

        # Act
        result = service._load_web_cache(cache_dir)

        # Assert
        assert result == {}

    def test_load_web_cache_returns_parsed_content_for_valid_file(self, tmp_path):
        """
        When .web_cache.json contains valid JSON with string values,
        _load_web_cache should parse and return the content.
        """
        # Arrange
        cache_dir = str(tmp_path / "session")
        cache_path = Path(cache_dir) / ".web_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        expected = {"https://example.com": "cached content"}
        cache_path.write_text(json.dumps(expected), encoding="utf-8")

        service = ContextService(
            file_system_manager=object(),
            repo_tree_generator=object(),
            environment_inspector=object(),
            llm_client=object(),
            web_scraper=object(),
        )

        # Act
        result = service._load_web_cache(cache_dir)

        # Assert
        assert result == expected

    def test_load_web_cache_returns_empty_dict_for_non_dict_structure(self, tmp_path):
        """
        When .web_cache.json contains valid JSON but it's not a dict
        (e.g., a list), _load_web_cache should return an empty dict.
        """
        # Arrange
        cache_dir = str(tmp_path / "session")
        cache_path = Path(cache_dir) / ".web_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text('["not", "a", "dict"]', encoding="utf-8")

        service = ContextService(
            file_system_manager=object(),
            repo_tree_generator=object(),
            environment_inspector=object(),
            llm_client=object(),
            web_scraper=object(),
        )

        # Act
        result = service._load_web_cache(cache_dir)

        # Assert
        assert result == {}

    def test_load_web_cache_returns_empty_dict_when_disabled(self, tmp_path):
        """
        When cache_dir is None, _load_web_cache should return an empty dict
        without attempting to read any file.
        """
        service = ContextService(
            file_system_manager=object(),
            repo_tree_generator=object(),
            environment_inspector=object(),
            llm_client=object(),
            web_scraper=object(),
        )

        # Act
        result = service._load_web_cache(None)

        # Assert
        assert result == {}


class TestSaveWebCache:
    """Tests for ContextService._save_web_cache private method."""

    def test_save_web_cache_creates_directory_and_writes_file(self, tmp_path):
        """
        When cache_dir does not exist, _save_web_cache should create it
        and write the cache content to .web_cache.json.
        """
        # Arrange
        cache_dir = str(tmp_path / "new_session")
        cache_content = {"https://example.com": "content"}

        service = ContextService(
            file_system_manager=object(),
            repo_tree_generator=object(),
            environment_inspector=object(),
            llm_client=object(),
            web_scraper=object(),
        )

        # Act
        service._save_web_cache(cache_dir, cache_content)

        # Assert
        cache_path = Path(cache_dir) / ".web_cache.json"
        assert cache_path.exists(), "Cache file should be created"
        loaded = json.loads(cache_path.read_text(encoding="utf-8"))
        assert loaded == cache_content

    def test_save_web_cache_overwrites_existing_file(self, tmp_path):
        """
        When .web_cache.json already exists, _save_web_cache should
        overwrite it with new content.
        """
        # Arrange
        cache_dir = str(tmp_path / "session")
        cache_dir_path = Path(cache_dir)
        cache_dir_path.mkdir(parents=True, exist_ok=True)
        initial = {"url1": "old"}
        initial_path = cache_dir_path / ".web_cache.json"
        initial_path.write_text(json.dumps(initial), encoding="utf-8")

        updated = {"url2": "new"}

        service = ContextService(
            file_system_manager=object(),
            repo_tree_generator=object(),
            environment_inspector=object(),
            llm_client=object(),
            web_scraper=object(),
        )

        # Act
        service._save_web_cache(cache_dir, updated)

        # Assert
        loaded = json.loads(initial_path.read_text(encoding="utf-8"))
        assert loaded == updated, "Cache file should contain new content"

    def test_save_web_cache_writes_correct_json_format(self, tmp_path):
        """
        The written .web_cache.json should be valid JSON with correct
        string keys and values.
        """
        # Arrange
        cache_dir = str(tmp_path / "session")
        cache_content = {
            "https://example.com/doc1": "content 1",
            "https://example.com/doc2": "content 2",
        }

        service = ContextService(
            file_system_manager=object(),
            repo_tree_generator=object(),
            environment_inspector=object(),
            llm_client=object(),
            web_scraper=object(),
        )

        # Act
        service._save_web_cache(cache_dir, cache_content)

        # Assert
        cache_path = Path(cache_dir) / ".web_cache.json"
        raw = cache_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert all(isinstance(k, str) for k in parsed)
        assert all(isinstance(v, str) for v in parsed.values())
        assert parsed == cache_content


class TestGetContextCacheIntegration:
    """
    Integration tests for the cache check in get_context()'s URL-fetching loop.

    These tests verify that the cache load/check/save lifecycle works correctly
    when get_context processes URLs from context_files.
    """

    def _make_service(self, tmp_path, web_scraper=None):
        """Create a ContextService with mocked dependencies for cache tests."""
        web_scraper = web_scraper or Mock(spec=IWebScraper)
        repo_tree = Mock(spec=IRepoTreeGenerator)
        repo_tree.generate_tree.return_value = ""

        env_inspector = Mock(spec=IEnvironmentInspector)
        env_inspector.get_environment_info.return_value = {}
        env_inspector.get_git_status.return_value = None

        llm_client = Mock(spec=ILlmClient)
        llm_client.get_text_token_count.return_value = 0

        file_system_manager = Mock(spec=IFileSystemManager)
        file_system_manager.read_files_in_vault.return_value = {}

        return ContextService(
            file_system_manager,
            repo_tree,
            env_inspector,
            llm_client,
            web_scraper,
        )

    def _setup_cache(self, tmp_path, contents: dict) -> str:
        """Create a session cache file with given contents, return cache_dir."""
        cache_dir = str(tmp_path / "session")
        cache_path = Path(cache_dir) / ".web_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(contents),
            encoding="utf-8",
        )
        return cache_dir

    def test_get_context_uses_cached_content_when_url_in_cache(self, tmp_path):
        """
        When a URL is already in the cache file, get_context should use
        the cached content and NOT call IWebScraper.get_content().
        """
        # Arrange
        url = "https://example.com/page"
        cached_content = "cached result"
        fresh_content = "fresh result"  # Should never be fetched

        cache_dir = self._setup_cache(tmp_path, {url: cached_content})
        web_scraper = Mock(spec=IWebScraper)
        web_scraper.get_content.return_value = fresh_content

        service = self._make_service(tmp_path, web_scraper)
        context_files = {"Session": [url]}

        # Act
        result = service.get_context(
            context_files=context_files,
            cache_dir=cache_dir,
        )

        # Assert: no network fetch occurred
        web_scraper.get_content.assert_not_called()

        # Assert: the cached content appears in the result
        assert cached_content in result.content, (
            f"Expected cached content '{cached_content}' in result"
        )
        assert fresh_content not in result.content, (
            f"Fresh content '{fresh_content}' should NOT be in result"
        )

    def test_get_context_fetches_and_caches_when_url_not_in_cache(self, tmp_path):
        """
        When a URL is NOT in the cache, get_context should fetch via
        IWebScraper, persist the content to the cache file, and return it.
        """
        # Arrange
        url = "https://example.com/page"
        fetched_content = "fresh fetched content"

        cache_dir = self._setup_cache(tmp_path, {})  # Empty cache
        web_scraper = Mock(spec=IWebScraper)
        web_scraper.get_content.return_value = fetched_content

        service = self._make_service(tmp_path, web_scraper)
        context_files = {"Session": [url]}

        # Act
        result = service.get_context(
            context_files=context_files,
            cache_dir=cache_dir,
        )

        # Assert: web scraper was called
        web_scraper.get_content.assert_called_once_with(url)

        # Assert: content is in the return value
        assert fetched_content in result.content, (
            f"Expected fetched content '{fetched_content}' in result"
        )

        # Assert: cache file now contains the URL
        cache_path = Path(cache_dir) / ".web_cache.json"
        assert cache_path.exists(), "Cache file should exist after fetch"
        stored = json.loads(cache_path.read_text(encoding="utf-8"))
        assert stored.get(url) == fetched_content, (
            f"Expected {url!r} -> {fetched_content!r} in cache, got {stored}"
        )

    def test_get_context_does_not_cache_failed_fetches(self, tmp_path):
        """
        When IWebScraper.get_content() raises an exception, the URL
        should NOT be added to the cache, allowing retries on subsequent calls.
        """
        # Arrange
        url = "https://example.com/failing-page"

        cache_dir = self._setup_cache(tmp_path, {})  # Empty cache
        web_scraper = Mock(spec=IWebScraper)
        web_scraper.get_content.side_effect = ConnectionError("Network timeout")

        service = self._make_service(tmp_path, web_scraper)
        context_files = {"Session": [url]}

        # Act
        result = service.get_context(
            context_files=context_files,
            cache_dir=cache_dir,
        )

        # Assert: web scraper was called
        web_scraper.get_content.assert_called_once_with(url)

        # Assert: content is None (represented as "--- FILE NOT FOUND ---") in result
        assert "--- FILE NOT FOUND ---" in result.content, (
            "Failed URL should appear as FILE NOT FOUND in result"
        )

        # Assert: cache file should NOT contain the failed URL
        cache_path = Path(cache_dir) / ".web_cache.json"
        assert cache_path.exists(), "Cache file should exist (created empty)"
        stored = json.loads(cache_path.read_text(encoding="utf-8"))
        assert url not in stored, f"Failed URL {url!r} should NOT be cached: {stored}"
