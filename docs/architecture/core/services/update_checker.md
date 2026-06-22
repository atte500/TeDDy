# Component Design: UpdateChecker

- **Status:** Validated (prototype confirmed)

## Purpose / Responsibility

Provides a lightweight, non-blocking mechanism to check for new TeDDy releases, cache the result locally, and conditionally perform upgrades. The service is designed as a utility module (not a port/adapter) to minimize architectural overhead while maintaining testability via module-level mocking.

## Failure Modes

- **Network Failure:** PyPI check fails (timeout, DNS, HTTP 5xx). The service MUST treat this as "no update" (fail silently) and NOT block CLI execution. Exceptions from `urllib.request` are caught at the boundary.
- **Cache Corruption:** `.teddy/.update_cache.json` is malformed. The service MUST treat this as an expired cache (ignore the file, re-fetch on next check).
- **Upgrade Failure:** `pip install` fails (permissions, network, dependency conflict). The service MUST catch `subprocess.CalledProcessError` and display a clear error message without crashing the CLI.
- **Import Failure (post-upgrade pre-warming):** If the heavy import pre-warming fails after a successful upgrade, the warning is logged but the CLI continues (pre-warming is a "best effort" optimization).

## Ports

- **Inbound:** Called directly by CLI commands (`__main__.py`) and session handlers (`session_cli_handlers.py`). No formal port interface.
- **Outbound:**
  - `urllib.request` (stdlib) for HTTP requests to PyPI/TestPyPI JSON API.
  - `subprocess` (stdlib) via `sys.executable -m pip` for upgrade execution.
  - Filesystem (via `pathlib`) for cache read/write at `.teddy/.update_cache.json`.
  - `importlib.metadata` for reading the current installed version.

## Implementation Details / Logic

The module contains the following top-level functions (all pure or with explicit side-effects):

1. **`get_current_version() -> str`**: Reads installed version from `importlib.metadata.version("teddy-cli")`. Returns `"0.0.0"` on failure (e.g., package not installed in dev mode).

2. **`fetch_latest_version(index_url: str = PYPI_URL) -> Optional[str]`**: Performs a GET request to the PyPI/TestPyPI JSON API. Parses the `"info"` -> `"version"` field. Returns `None` on any exception.

3. **`compare_versions(current: str, latest: str) -> bool`**: Returns `True` if `latest > current` using `packaging.version.Version` comparison.

4. **`read_update_cache(cache_path: Path) -> Optional[dict]`**: Reads the JSON cache file, validates structure (must contain `latest_version` and `checked_at`). Returns `None` if file is missing, corrupt, or TTL exceeded (24h).

5. **`write_update_cache(cache_path: Path, latest_version: str) -> None`**: Atomically writes the cache file (write to temp, rename).

6. **`perform_upgrade(latest_version: str, index_url: str = PYPI_URL) -> bool`**: Runs `sys.executable -m pip install --upgrade teddy-cli` with optional `--index-url` for TestPyPI. Returns `True` on success.

**7. `should_update(cache_path: Path, auto_update_enabled: bool = False) -> Optional[bool]`**: High-level check: read cache -> if valid and newer version, respect `auto_update` setting. Returns `True` (proceed with upgrade), `False` (notify only), or `None` (no action needed). The `auto_update_enabled` boolean is read from `IConfigService.get_setting("auto_update")` by the calling CLI code and passed directly — `should_update` does NOT accept or depend on a config service.

**8. `prewarm_imports() -> None`**: Extracted from `__main__.py` init command into `cli_helpers.py`. Tries to import heavy packages (`litellm`, `trafilatura`, `pyperclip`, `BeautifulSoup`, `DDGS`). Silently ignores `ImportError`. Called by both `init` command (pre-existing) and `update` command (after successful upgrade).

All functions use stdlib only (plus `packaging` which is a transitive dependency). No new external dependencies. The `prewarm_imports` function lives in `cli_helpers.py` (not `update_checker.py`) because it is shared with the `init` command.

## Data Contracts / Methods

```python
PYPI_URL = "https://pypi.org/pypi/teddy-cli/json"
TEST_PYPI_URL = "https://test.pypi.org/pypi/teddy-cli/json"
CACHE_FILENAME = ".update_cache.json"
CACHE_TTL_HOURS = 24

def get_current_version() -> str: ...

def fetch_latest_version(index_url: str = PYPI_URL) -> str | None: ...

def compare_versions(current: str, latest: str) -> bool:
    """Returns True if latest > current. Returns False on any parse failure
    (invalid version strings, empty strings, or equal versions)."""

def read_update_cache(cache_path: Path) -> dict | None: ...

def write_update_cache(cache_path: Path, latest_version: str) -> None: ...

def perform_upgrade(latest_version: str, index_url: str = PYPI_URL) -> bool: ...

def should_update(cache_path: Path, auto_update_enabled: bool = False) -> bool | None:
    """Returns True (upgrade now), False (notify only), or None (no action)."""

# Located in cli_helpers.py (shared with init command):
def prewarm_imports() -> None: ...
```
