"""Fake persistent model-registry cache for hydrator tests.

The fake models the persistent OpenRouter model-registry cache file
state validated by the prototype (spikes/prototypes/windows-startup-latency/
registry_cache_prototype.py):

- JSON file at <root>/.teddy/.model_registry_cache.json
- Payload keys: version (int, 1), fetched_at_epoch (int epoch seconds),
  models (raw OpenRouter catalog entries)
- Expiry boundary: now - fetched_at_epoch >= ttl is expired
- States: missing (default) / fresh / expired / corrupt

State is backed by REAL files in a temp directory (tempfile.mkdtemp per
the architecture's temp-file standard) because the hydrator under test
reads and writes a real path; dynamic mock objects would not exercise
the actual file semantics.
"""

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

CACHE_FILENAME = ".model_registry_cache.json"
PAYLOAD_VERSION = 1


class FakeRegistryCache:
    """File-state fake for the persistent OpenRouter registry cache.

    Context-manager usage guarantees zero filesystem residue: the temp
    root is removed on exit.
    """

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="teddy-fake-registry-cache-"))
        self.teddy_dir = self.root / ".teddy"
        self.teddy_dir.mkdir()
        self.cache_path = self.teddy_dir / CACHE_FILENAME

    def __enter__(self) -> "FakeRegistryCache":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def write_fresh(
        self,
        models: List[Dict[str, Any]],
        fetched_at: Optional[int] = None,
    ) -> None:
        """Writes a fresh cache payload with the given catalog entries.

        fetched_at defaults to the current epoch second (fresh state);
        pass an explicit epoch to pin the payload for TTL-boundary tests.
        """
        payload = {
            "version": PAYLOAD_VERSION,
            "fetched_at_epoch": (
                fetched_at if fetched_at is not None else int(time.time())
            ),
            "models": models,
        }
        self.cache_path.write_text(json.dumps(payload), encoding="utf-8")

    def expire(self, ttl_seconds: int) -> None:
        """Rewrites fetched_at_epoch so the payload sits exactly ON the
        expiry boundary (now - fetched_at_epoch == ttl_seconds), for
        TTL-boundary tests of the real cache loader."""
        payload = self.read_payload()
        payload["fetched_at_epoch"] = int(time.time()) - ttl_seconds
        self.cache_path.write_text(json.dumps(payload), encoding="utf-8")

    def corrupt(self) -> None:
        """Overwrites the cache file with unparsable content."""
        self.cache_path.write_text("{not json at all", encoding="utf-8")

    def remove(self) -> None:
        """Deletes the cache file (back to the missing state)."""
        self.cache_path.unlink(missing_ok=True)

    def read_payload(self) -> Dict[str, Any]:
        """Reads and parses the raw cache payload as JSON."""
        return json.loads(self.cache_path.read_text(encoding="utf-8"))
