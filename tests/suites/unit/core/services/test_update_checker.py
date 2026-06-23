"""Unit tests for update_checker.py core functions."""

from teddy_executor.core.services.update_checker import compare_versions


class TestCompareVersions:
    """Tests for the compare_versions pure function."""

    def test_newer_version_returns_true(self):
        assert compare_versions("1.0.0", "2.0.0") is True

    def test_older_version_returns_false(self):
        assert compare_versions("2.0.0", "1.0.0") is False

    def test_equal_version_returns_false(self):
        assert compare_versions("1.0.0", "1.0.0") is False

    def test_invalid_current_version_returns_false(self):
        assert compare_versions("abc", "1.0.0") is False

    def test_invalid_latest_version_returns_false(self):
        assert compare_versions("1.0.0", "abc") is False

    def test_both_empty_returns_false(self):
        assert compare_versions("", "") is False

    def test_current_empty_latest_valid_returns_false(self):
        # Empty string can't be parsed as PEP 440, so returns False
        assert compare_versions("", "1.0.0") is False


class TestGetCurrentVersion:
    """Tests for get_current_version function."""

    def test_returns_mocked_version(self, monkeypatch):
        """Should return the version string from importlib.metadata."""
        monkeypatch.setattr("importlib.metadata.version", lambda pkg: "42.0.0")
        from teddy_executor.core.services.update_checker import get_current_version

        result = get_current_version()
        assert result == "42.0.0"

    def test_fallback_on_package_not_found(self, monkeypatch):
        """Should return "0.0.0" when importlib.metadata raises Exception."""
        monkeypatch.setattr(
            "importlib.metadata.version",
            lambda pkg: (_ for _ in ()).throw(Exception("Not found")),
        )
        from teddy_executor.core.services.update_checker import get_current_version

        result = get_current_version()
        assert result == "0.0.0"


class TestFetchLatestVersion:
    """Tests for fetch_latest_version function."""

    def test_returns_version_from_pypi_response(self, monkeypatch):
        """Should parse the version from a simulated PyPI JSON response."""
        import json
        import urllib.request
        from tests.harness.setup.fake_http_response import FakeHTTPResponse

        mock_response = FakeHTTPResponse(
            data=json.dumps({"info": {"version": "42.0.0"}}),
            status_code=200,
        )

        def mock_urlopen(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        from teddy_executor.core.services.update_checker import fetch_latest_version

        result = fetch_latest_version()
        assert result == "42.0.0"

    def test_returns_none_on_network_error(self, monkeypatch):
        """Should return None when urllib raises URLError."""
        import urllib.request
        import urllib.error

        def mock_urlopen(*args, **kwargs):
            raise urllib.error.URLError("Network error")

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        from teddy_executor.core.services.update_checker import fetch_latest_version

        result = fetch_latest_version()
        assert result is None

    def test_returns_none_on_invalid_json(self, monkeypatch):
        """Should return None when response body is not valid JSON."""
        import urllib.request
        from tests.harness.setup.fake_http_response import FakeHTTPResponse

        mock_response = FakeHTTPResponse(
            data="not json",
            status_code=200,
        )

        def mock_urlopen(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        from teddy_executor.core.services.update_checker import fetch_latest_version

        result = fetch_latest_version()
        assert result is None

    def test_returns_none_on_missing_version_key(self, monkeypatch):
        """Should return None when 'info.version' is missing from response."""
        import json
        import urllib.request
        from tests.harness.setup.fake_http_response import FakeHTTPResponse

        mock_response = FakeHTTPResponse(
            data=json.dumps({"info": {}}),
            status_code=200,
        )

        def mock_urlopen(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        from teddy_executor.core.services.update_checker import fetch_latest_version

        result = fetch_latest_version()
        assert result is None


class TestReadUpdateCache:
    """Tests for read_update_cache function."""

    def test_returns_data_on_valid_cache(self, temp_cache_dir):
        """Should return parsed data when cache file is valid and not expired."""
        import json
        from datetime import datetime, timezone, timedelta
        from teddy_executor.core.services.update_checker import read_update_cache

        cache_path = temp_cache_dir / ".update_cache.json"
        cache_data = {
            "latest_version": "1.0.0",
            "checked_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        result = read_update_cache(cache_path)
        assert result is not None
        assert result["latest_version"] == "1.0.0"

    def test_returns_none_on_missing_file(self, temp_cache_dir):
        """Should return None when cache file does not exist."""
        from teddy_executor.core.services.update_checker import read_update_cache

        cache_path = temp_cache_dir / ".update_cache.json"
        # Do not create the file
        result = read_update_cache(cache_path)
        assert result is None

    def test_returns_none_on_corrupt_json(self, temp_cache_dir):
        """Should return None when cache file contains invalid JSON."""
        from teddy_executor.core.services.update_checker import read_update_cache

        cache_path = temp_cache_dir / ".update_cache.json"
        cache_path.write_text("not valid json{{{", encoding="utf-8")

        result = read_update_cache(cache_path)
        assert result is None

    def test_returns_none_on_expired_cache(self, temp_cache_dir):
        """Should return None when cache TTL has been exceeded."""
        import json
        from datetime import datetime, timezone, timedelta
        from teddy_executor.core.services.update_checker import (
            read_update_cache,
            CACHE_TTL_HOURS,
        )

        cache_path = temp_cache_dir / ".update_cache.json"
        cache_data = {
            "latest_version": "1.0.0",
            "checked_at": (
                datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS + 1)
            ).isoformat(),
        }
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        result = read_update_cache(cache_path)
        assert result is None

    def test_returns_none_on_missing_keys(self, temp_cache_dir):
        """Should return None when cache data is missing required keys."""
        import json
        from teddy_executor.core.services.update_checker import read_update_cache

        cache_path = temp_cache_dir / ".update_cache.json"
        # Missing 'checked_at'
        cache_path.write_text(json.dumps({"latest_version": "1.0.0"}), encoding="utf-8")

        result = read_update_cache(cache_path)
        assert result is None


class TestWriteUpdateCache:
    """Tests for write_update_cache function."""

    def test_writes_cache_file(self, temp_cache_dir):
        """Should create a cache file with latest_version and checked_at."""
        from teddy_executor.core.services.update_checker import write_update_cache

        cache_path = temp_cache_dir / ".update_cache.json"
        write_update_cache(cache_path, "2.0.0")

        assert cache_path.is_file()
        import json

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["latest_version"] == "2.0.0"
        assert "checked_at" in data

    def test_creates_parent_directory(self, temp_cache_dir):
        """Should create parent directories if they don't exist."""
        from teddy_executor.core.services.update_checker import write_update_cache

        cache_path = temp_cache_dir / "subdir" / "nested" / ".update_cache.json"
        write_update_cache(cache_path, "3.0.0")

        assert cache_path.is_file()
        import json

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["latest_version"] == "3.0.0"

    def test_atomic_write_uses_temp_file(self, temp_cache_dir):
        """Should write to a .tmp file first, then rename to the final path."""
        from teddy_executor.core.services.update_checker import write_update_cache

        cache_path = temp_cache_dir / ".update_cache.json"
        tmp_path = cache_path.with_suffix(".tmp")

        write_update_cache(cache_path, "4.0.0")

        # The .tmp file should NOT exist after the write (it was renamed)
        assert cache_path.is_file()
        assert not tmp_path.exists()


class TestBackgroundCheck:
    """Tests for background_check function."""

    def test_fetches_and_writes_cache(self, monkeypatch, temp_cache_dir):
        """Should fetch latest version and write to cache."""
        from teddy_executor.core.services.update_checker import background_check

        def mock_fetch(index_url=None):
            return "5.0.0"

        monkeypatch.setattr(
            "teddy_executor.core.services.update_checker.fetch_latest_version",
            mock_fetch,
        )

        cache_path = temp_cache_dir / ".update_cache.json"
        background_check(cache_path)

        import json

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["latest_version"] == "5.0.0"
        assert "checked_at" in data

    def test_does_not_write_cache_on_fetch_failure(self, monkeypatch, temp_cache_dir):
        """Should not create cache file when fetch returns None."""
        from teddy_executor.core.services.update_checker import background_check

        def mock_fetch(index_url=None):
            return None

        monkeypatch.setattr(
            "teddy_executor.core.services.update_checker.fetch_latest_version",
            mock_fetch,
        )

        cache_path = temp_cache_dir / ".update_cache.json"
        background_check(cache_path)

        assert not cache_path.exists()
