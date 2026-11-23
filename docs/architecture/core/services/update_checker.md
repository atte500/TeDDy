# Component Design: UpdateChecker
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/update_checker.py`](/src/teddy_executor/core/services/update_checker.py)

## Purpose
A lightweight utility module that checks for new TeDDy releases and caches the result locally. It runs the network check in a background thread and surfaces an upgrade instruction without ever upgrading automatically. It is a plain module rather than a port and adapter to minimize architectural overhead.

## Consumers
- [CLI Adapter](../../adapters/inbound/cli.md): Serves the `update` command and the session startup notice through `__main__.py` and the session CLI handlers.

## Dependencies
- `urllib.request` (stdlib): Performs the PyPI JSON API request.
- `pathlib` (stdlib): Reads and writes the update cache.
- `importlib.metadata` (stdlib): Reads the installed package version.
- `packaging.version.Version` (external): Compares PEP 440 versions.
- `certifi` (external, optional): Supplies the CA bundle when available.

## Class Invariants
- `fail_silent`: A network failure returns `None` and never blocks CLI execution.
- `atomic_cache_write`: The cache is written to a temporary file and renamed, so a reader never sees a partial file.
- `ttl_bound_cache`: A cache entry older than 24 hours is treated as absent.
- `stdlib_only`: Every public function uses only the standard library plus `packaging`.
- `caller_owned_source`: The module never reads configuration; callers resolve `update.index_url` through `IConfigService` and pass the resolved URL in. `PYPI_URL` is only the fallback inside `resolve_index_url`.

## Inbound Ports
None — this module exposes plain functions, not a port.

## Outbound Ports
None — the module calls the standard library directly and declares no injected ports.

## Data Contracts
- **Constants:** `PYPI_URL = "https://pypi.org/pypi/teddy-cli/json"` (the fallback source), `CACHE_FILENAME = ".update_cache.json"`, `CACHE_TTL_HOURS = 24`.
- **Cache file mapping:** `latest_version: str`, `checked_at: str` (ISO 8601 UTC).
- **Update source:** `update.index_url` (declared config key, default `""`). Callers resolve it through `IConfigService` and pass the result to `fetch_latest_version` / `background_check`; the module never reads configuration itself.

## Operations

### `get_current_version() -> str`
- **Postconditions:** Returns the installed `teddy-cli` version, or `"0.0.0"` when the package metadata is unavailable.

### `resolve_index_url(configured) -> str`
- **Postconditions:** Returns `configured` stripped of surrounding whitespace, or `PYPI_URL` when `configured` is `None`, empty, or whitespace-only. Owns the official-endpoint fallback exactly once, so no call site repeats `or PYPI_URL`.

### `fetch_latest_version(index_url=PYPI_URL, stable_only=True) -> Optional[str]`
- **Postconditions:** Returns the highest matching version from the PyPI JSON API at `index_url`, filtering pre-releases when `stable_only` is `True`, and falling back to `info.version` when the source returns no `releases` map. That fallback ignores `stable_only`, so a static source reports the same version with or without `--experimental`. Returns `None` on any network or parse failure.

### `is_prerelease(version_str) -> bool`
- **Postconditions:** Returns `True` for a PEP 440 pre-release, and `False` on any parse failure.

### `compare_versions(current, latest) -> bool`
- **Postconditions:** Returns `True` when `latest > current`, and `False` on any parse failure or equality.

### `read_update_cache(cache_path) -> Optional[dict]`
- **Postconditions:** Returns the cached mapping when it is present, well-formed, and within the TTL. Returns `None` when the file is missing, corrupt, malformed, or expired.

### `write_update_cache(cache_path, latest_version) -> None`
- **Postconditions:** Atomically writes the cache file, creating the parent directory when needed. The write is best-effort: a directory-creation or write `OSError` is logged at debug level and swallowed.

### `background_check(cache_path, index_url=PYPI_URL) -> None`
- **Postconditions:** Fetches the latest version from `index_url` and writes it to cache. Intended to run in a daemon thread and swallows every error. The caller passes the resolved source, so the daemon never touches the container.

**Note:** The `prewarm_imports` helper lives in [`cli_helpers.py`](/src/teddy_executor/adapters/inbound/cli_helpers.py), not this module, because it is shared with the `init` command.
