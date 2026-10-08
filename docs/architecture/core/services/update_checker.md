# Component Design: UpdateChecker

- **Status:** Validated (prototype confirmed)

## Purpose / Responsibility

Provides a lightweight, non-blocking mechanism to check for new TeDDy releases and cache the result locally. The service is designed as a utility module (not a port/adapter) to minimize architectural overhead while maintaining testability via module-level mocking. The `update` command is notification-only: it surfaces an upgrade instruction but never upgrades automatically.

## Failure Modes

- **Network Failure:** PyPI check fails (timeout, DNS, HTTP 5xx). The service MUST treat this as "no update" (fail silently) and NOT block CLI execution. Exceptions from `urllib.request` are caught at the boundary.
- **Cache Corruption:** `.teddy/.update_cache.json` is malformed. The service MUST treat this as an expired cache (ignore the file, re-fetch on next check).
- **Stale Index:** The checker reads a package index that no longer receives new releases. Dev pre-releases are published to PyPI (see `.github/workflows/publish.yml`), so the check MUST query `PYPI_URL` for both the stable and experimental channels and never a retired index.

## Ports

- **Inbound:** Called directly by CLI commands (`__main__.py`) and session handlers (`session_cli_handlers.py`). No formal port interface.
- **Outbound:**
  - `urllib.request` (stdlib) for HTTP requests to the PyPI JSON API.
  - Filesystem (via `pathlib`) for cache read/write at `.teddy/.update_cache.json`.
  - `importlib.metadata` for reading the current installed version.

## Implementation Details / Logic

The module contains the following top-level functions (all pure or with explicit side-effects):

1. **`get_current_version() -> str`**: Reads installed version from `importlib.metadata.version("teddy-cli")`. Returns `"0.0.0"` on failure (e.g., package not installed in dev mode).

2. **`fetch_latest_version(index_url: str = PYPI_URL, stable_only: bool = True) -> Optional[str]`**: Performs a GET request to the PyPI JSON API, scans `data["releases"]`, and returns the highest version — filtering out pre-releases when `stable_only=True`. Returns `None` on any exception.

3. **`is_prerelease(version_str: str) -> bool`**: Returns `True` if the version is a pre-release (dev/alpha/beta/rc) per PEP 440. Returns `False` on any parse failure.

4. **`compare_versions(current: str, latest: str) -> bool`**: Returns `True` if `latest > current` using `packaging.version.Version` comparison.

5. **`read_update_cache(cache_path: Path) -> Optional[dict]`**: Reads the JSON cache file, validates structure (must contain `latest_version` and `checked_at`). Returns `None` if file is missing, corrupt, or TTL exceeded (24h).

6. **`write_update_cache(cache_path: Path, latest_version: str) -> None`**: Atomically writes the cache file (write to temp, rename).

7. **`background_check(cache_path: Path, index_url: str = PYPI_URL) -> None`**: Non-blocking version check intended to run in a daemon thread. Fetches the latest version and writes it to cache.

All functions use stdlib only (plus `packaging` which is a transitive dependency). The `prewarm_imports` helper lives in `cli_helpers.py` (not `update_checker.py`) because it is shared with the `init` command.

## Data Contracts / Methods

```python
PYPI_URL = "https://pypi.org/pypi/teddy-cli/json"
CACHE_FILENAME = ".update_cache.json"
CACHE_TTL_HOURS = 24

def get_current_version() -> str: ...

def fetch_latest_version(index_url: str = PYPI_URL, stable_only: bool = True) -> str | None: ...

def is_prerelease(version_str: str) -> bool: ...

def compare_versions(current: str, latest: str) -> bool:
    """Returns True if latest > current. Returns False on any parse failure
    (invalid version strings, empty strings, or equal versions)."""

def read_update_cache(cache_path: Path) -> dict | None: ...

def write_update_cache(cache_path: Path, latest_version: str) -> None: ...

def background_check(cache_path: Path, index_url: str = PYPI_URL) -> None: ...

# Located in cli_helpers.py (shared with init command):
def prewarm_imports() -> None: ...
```
