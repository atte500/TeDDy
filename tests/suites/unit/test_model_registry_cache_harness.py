"""Harness self-tests for the FakeRegistryCache test double.

The fake models the persistent OpenRouter model-registry cache file state
validated by the prototype (spikes/prototypes/windows-startup-latency/
registry_cache_prototype.py, 7/7 PASS):

- JSON file at <root>/.teddy/.model_registry_cache.json
- Payload keys: version (int, 1), fetched_at_epoch (int epoch seconds),
  models (raw OpenRouter catalog entries)
- Expiry boundary: now - fetched_at_epoch >= ttl is expired
- States: missing (default) / fresh / expired / corrupt

The fake backs state with REAL files in a temp directory because the
hydrator under test reads and writes a real path; dynamic mock objects
would not exercise the actual file semantics (anti-mock-poisoning: state
is faked with real files, not mocks).
"""

import json
import time

import pytest

from tests.harness.setup.model_registry_cache import (
    CACHE_FILENAME,
    PAYLOAD_VERSION,
    FakeRegistryCache,
)
from tests.harness.setup.openrouter_mock_data import OPENROUTER_MODELS_RESPONSE


@pytest.fixture
def cache():
    with FakeRegistryCache() as fake:
        yield fake


class TestCacheFileLocation:
    """The cache path and directory layout match the validated spec."""

    def test_cache_filename_matches_spec(self):
        assert CACHE_FILENAME == ".model_registry_cache.json"

    def test_cache_path_is_under_teddy_dir(self, cache):
        assert cache.cache_path.parent == cache.teddy_dir
        assert cache.cache_path.name == CACHE_FILENAME

    def test_teddy_dir_layout_matches_spec(self, cache):
        assert cache.teddy_dir == cache.root / ".teddy"

    def test_teddy_dir_exists_on_construction(self, cache):
        assert cache.teddy_dir.is_dir()


class TestPayloadStates:
    """Payload shape, round-trip fidelity, and the four cache states."""

    def test_cache_file_is_missing_by_default(self, cache):
        assert not cache.cache_path.exists()

    def test_write_fresh_round_trips_catalog_models(self, cache):
        models = OPENROUTER_MODELS_RESPONSE["data"]

        cache.write_fresh(models)

        payload = cache.read_payload()
        assert set(payload) == {"version", "fetched_at_epoch", "models"}
        assert payload["version"] == PAYLOAD_VERSION
        assert payload["models"] == models

    def test_write_fresh_fetched_at_defaults_to_now(self, cache):
        before = int(time.time())

        cache.write_fresh([{"id": "openrouter/x"}])

        fetched = cache.read_payload()["fetched_at_epoch"]
        assert before <= fetched <= int(time.time())

    def test_write_fresh_accepts_explicit_fetched_at(self, cache):
        cache.write_fresh([{"id": "openrouter/x"}], fetched_at=1_700_000_000)

        assert cache.read_payload()["fetched_at_epoch"] == 1_700_000_000

    def test_expire_sets_fetched_at_beyond_ttl_boundary(self, cache):
        ttl = 7 * 24 * 3600

        cache.write_fresh([{"id": "openrouter/x"}])
        cache.expire(ttl_seconds=ttl)

        fetched = cache.read_payload()["fetched_at_epoch"]
        assert int(time.time()) - fetched >= ttl

    def test_corrupt_writes_unparsable_content(self, cache):
        cache.write_fresh([{"id": "openrouter/x"}])

        cache.corrupt()

        assert cache.cache_path.exists()
        with pytest.raises(json.JSONDecodeError):
            json.loads(cache.cache_path.read_text(encoding="utf-8"))

    def test_remove_deletes_cache_file(self, cache):
        cache.write_fresh([{"id": "openrouter/x"}])

        cache.remove()

        assert not cache.cache_path.exists()


class TestCleanup:
    """The fake must leave no filesystem residue behind."""

    def test_context_manager_removes_temp_root(self):
        with FakeRegistryCache() as fake:
            root = fake.root
            assert root.is_dir()

        assert not root.exists()
