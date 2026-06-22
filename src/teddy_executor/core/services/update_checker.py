"""Update Checker: Lightweight version check and upgrade mechanism.

Provides functions for detecting the current installed version, fetching the
latest version from PyPI/TestPyPI, comparing versions, caching results, and
performing upgrades. All public functions use stdlib only (plus the
`packaging` library which is a transitive dependency via pip-audit).
"""

from __future__ import annotations

from typing import Optional

from packaging.version import Version

# --- Constants ---

PYPI_URL = "https://pypi.org/pypi/teddy-cli/json"
TEST_PYPI_URL = "https://test.pypi.org/pypi/teddy-cli/json"
CACHE_FILENAME = ".update_cache.json"
CACHE_TTL_HOURS = 24


# --- Public API ---


def get_current_version() -> str:
    """
    Read installed version from importlib.metadata.
    Falls back to '0.0.0' for dev installations or missing package.
    """
    try:
        from importlib.metadata import version as _get_version

        return _get_version("teddy-cli")
    except Exception:
        return "0.0.0"


def fetch_latest_version(index_url: str = PYPI_URL) -> Optional[str]:
    """
    Fetch latest version from PyPI/TestPyPI JSON API.
    Returns None on any failure (network, parse, etc.) — silent fallback.
    """
    import json
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            index_url,
            headers={
                "User-Agent": "TeDDy-Update-Checker/1.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("info", {}).get("version")
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
        return None


def compare_versions(current: str, latest: str) -> bool:
    """
    Returns True if latest > current using PEP 440 version comparison.
    Returns False on any parse failure.
    """
    try:
        return Version(latest) > Version(current)
    except Exception:
        return False


def read_update_cache(cache_path: Path) -> Optional[dict]:
    """
    Read the cache file. Returns None if:
    - File is missing
    - File is corrupt (invalid JSON)
    - File has invalid structure (missing keys)
    - TTL exceeded (24h from checked_at)
    """
    import json
    from datetime import datetime, timezone, timedelta

    try:
        if not cache_path.is_file():
            return None
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if "latest_version" not in data or "checked_at" not in data:
            return None
        checked_at = datetime.fromisoformat(data["checked_at"])
        if datetime.now(timezone.utc) - checked_at > timedelta(hours=CACHE_TTL_HOURS):
            return None
        return data
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return None


def write_update_cache(cache_path: Path, latest_version: str) -> None:
    """
    Atomically write the cache file (write to temp file, rename).
    Ensures the main thread never reads a partially written file.
    """
    import json
    from datetime import datetime, timezone

    cache_data = {
        "latest_version": latest_version,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        tmp_path.rename(cache_path)
    except OSError as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug("Failed to write update cache: %s", e)
        if tmp_path.exists():
            tmp_path.unlink()


def perform_upgrade(latest_version: str, index_url: str = PYPI_URL) -> bool:
    """
    Run pip install --upgrade for the package.
    Uses sys.executable to ensure the correct Python environment.

    Args:
        latest_version: The version string being upgraded to (for logging).
        index_url: PyPI URL (default) or TestPyPI URL for experimental flag.

    Returns:
        True if upgrade succeeded, False otherwise.
    """
    import subprocess
    import sys

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "teddy-cli"]
    if index_url != PYPI_URL:
        cmd.extend(["--index-url", index_url])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            import logging

            logger = logging.getLogger(__name__)
            logger.error("Upgrade failed: %s", result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        import logging

        logger = logging.getLogger(__name__)
        logger.error("Upgrade timed out after 120 seconds")
        return False
    except OSError as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error("Could not run pip: %s", e)
        return False


def background_check(cache_path: Path, index_url: str = PYPI_URL) -> None:
    """
    Non-blocking background version check.
    Intended to run in a daemon thread. Fetches latest version from PyPI
    and writes it to cache. All errors are silently caught.
    """
    latest = fetch_latest_version(index_url)
    if latest is not None:
        write_update_cache(cache_path, latest)


def should_update(
    cache_path: Path,
    auto_update_enabled: bool = False,
) -> Optional[bool]:
    """
    High-level check: read cache, compare versions, respect auto_update setting.

    Args:
        cache_path: Path to the cache file.
        auto_update_enabled: Whether auto_update is enabled in config.

    Returns:
        - True  → update should proceed (newer version + auto_update enabled)
        - False → newer version available but auto_update disabled
        - None  → no update needed or version check failed
    """
    cache = read_update_cache(cache_path)
    if cache is None:
        return None
    current = get_current_version()
    latest = cache["latest_version"]
    if not compare_versions(current, latest):
        return None
    return auto_update_enabled
