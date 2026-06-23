"""Update Checker: Lightweight version check and upgrade mechanism.

Provides functions for detecting the current installed version, fetching the
latest version from PyPI/TestPyPI, comparing versions, caching results, and
performing upgrades. All public functions use stdlib only (plus the
`packaging` library which is a transitive dependency via pip-audit).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from packaging.version import Version

if TYPE_CHECKING:
    import ssl

# --- Constants ---

PYPI_URL = "https://pypi.org/pypi/teddy-cli/json"
TEST_PYPI_URL = "https://test.pypi.org/pypi/teddy-cli/json"
CACHE_FILENAME = ".update_cache.json"
CACHE_TTL_HOURS = 24


# --- SSL Context Setup ---


def _create_ssl_context() -> ssl.SSLContext:
    """
    Create an SSL context with proper CA bundle.

    Priority order:
    1. certifi if available (provides latest Mozilla CA bundle)
    2. Default SSL context (system CA bundle)

    Returns an ssl.SSLContext object suitable for urllib.
    """
    import ssl  # noqa: F811  (imported at module level under TYPE_CHECKING)

    try:
        import certifi

        cafile = certifi.where()
        if Path(cafile).is_file():
            return ssl.create_default_context(cafile=cafile)
    except ImportError:
        pass

    # Fallback: use system default (may fail on some Python 3.14 macOS builds)
    return ssl.create_default_context()


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


def fetch_latest_version(
    index_url: str = PYPI_URL,
    stable_only: bool = True,
) -> Optional[str]:
    """
    Fetch the highest version from PyPI/TestPyPI JSON API.

    Scans all releases in data['releases'] (instead of only data['info']['version']),
    and optionally filters to stable versions only.

    Args:
        index_url: The PyPI JSON API URL.
        stable_only: If True (default), only consider stable (non-prerelease) versions.
                     If False, consider all versions including dev/pre-releases.

    Returns:
        The highest matching version string, or None on failure.
    """
    import json
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(
            index_url,
            headers={
                "User-Agent": "TeDDy-Update-Checker/1.0",
                "Accept": "application/json",
            },
        )
        context = _create_ssl_context()
        with urllib.request.urlopen(req, timeout=10, context=context) as resp:  # nosec
            data = json.loads(resp.read().decode("utf-8"))
            releases = data.get("releases", {})
            if not releases:
                # Fallback to info.version if releases dict is empty
                return data.get("info", {}).get("version")
            valid_versions = []
            for v_str in releases.keys():
                try:
                    ver = Version(v_str)
                    if stable_only and ver.is_prerelease:
                        continue
                    valid_versions.append(ver)
                except Exception:
                    pass
            if not valid_versions:
                return None
            highest = max(valid_versions)
            return str(highest)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug("fetch_latest_version failed: %s", e)
        return None


def is_prerelease(version_str: str) -> bool:
    """
    Returns True if the given version string is a pre-release (dev, alpha, beta, rc, etc.)
    according to PEP 440. Returns False on any parse failure.
    """
    try:
        return Version(version_str).is_prerelease
    except Exception:
        return False


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
    if cache_path is None:
        return None
    cache = read_update_cache(cache_path)
    if cache is None:
        return None
    current = get_current_version()
    latest = cache["latest_version"]
    if not compare_versions(current, latest):
        return None
    return auto_update_enabled
