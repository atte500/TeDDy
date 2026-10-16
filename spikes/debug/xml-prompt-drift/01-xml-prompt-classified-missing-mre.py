"""MRE: a same-stem `.xml` prompt must be reported as DRIFTED, not MISSING.

Reproduces the bug where ``.teddy/prompts/`` holds the six agent prompts as
pre-migration ``.xml`` files and no ``.md`` files. ``ensure_initialized`` skips
copying the ``.md`` prompts (a same-stem ``.xml`` counts as present), so the
drift check then classifies every prompt as MISSING instead of DIFFERING.

Run: uv run python spikes/debug/xml-prompt-drift/01-xml-prompt-classified-missing-mre.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

# Select the implementation under test: "production" (default) loads the real
# module from src/; "replica" loads the sandbox replica carrying the proposed fix.
_IMPL = sys.argv[1] if len(sys.argv) > 1 else "production"

if _IMPL == "replica":
    _replica_path = Path(__file__).resolve().parent / "replica_init_service.py"
    _spec = importlib.util.spec_from_file_location(
        "replica_init_service", _replica_path
    )
    assert _spec is not None and _spec.loader is not None
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    InitService = _module.InitService
    _PROMPT_FILES = _module._PROMPT_FILES
    _TEMPLATE_FILES = _module._TEMPLATE_FILES
else:
    from teddy_executor.core.services.init_service import (  # noqa: E402
        InitService,
        _PROMPT_FILES,
        _TEMPLATE_FILES,
    )


class FakeFileSystem:
    """Minimal in-memory stand-in for the IFileSystemManager outbound port."""

    def __init__(self, existing: set[str], contents: dict[str, str]) -> None:
        self._existing = set(existing)
        self._contents = dict(contents)

    def path_exists(self, path: str) -> bool:
        return path in self._existing

    def read_file(self, path: str) -> str:
        return self._contents[path]

    def list_directory(self, path: str) -> list[str]:
        prefix = path.rstrip("/") + "/"
        return sorted(
            p[len(prefix) :]
            for p in self._existing
            if p.startswith(prefix) and "/" not in p[len(prefix) :]
        )

    def create_directory(self, path: str) -> None:
        self._existing.add(path)

    def write_file(self, path: str, content: str) -> None:
        self._existing.add(path)
        self._contents[path] = content

    def remove_file(self, path: str) -> None:
        self._existing.discard(path)
        self._contents.pop(path, None)


CONFIG_DIR = "bundled/config"
TEMPLATES_DIR = "bundled/templates"


def _build_fs() -> FakeFileSystem:
    """Builds the exact user scenario: six `.xml` prompts, no `.md` prompts."""
    existing: set[str] = set()
    contents: dict[str, str] = {}

    # Bundled prompt defaults (the .md manifest) exist inside the package.
    for name in _PROMPT_FILES:
        path = f"{CONFIG_DIR}/prompts/{name}"
        existing.add(path)
        contents[path] = f"# {name}\n\nbundled default content\n"

    # Bundled + user templates exist and match, so the templates channel is clean.
    for name in _TEMPLATE_FILES:
        bundled = f"{TEMPLATES_DIR}/{name}"
        user = f"docs/templates/{name}"
        existing.add(bundled)
        existing.add(user)
        contents[bundled] = f"# {name}\n"
        contents[user] = f"# {name}\n"

    # The user migrated from the XML era: only pre-migration .xml files exist,
    # exactly what ensure_initialized(overwrite=False) leaves in place. The
    # directory entries are registered too, because the real filesystem reports
    # a populated directory as existing and the drift check guards its
    # directory scan on that existence.
    existing.add(".teddy")
    existing.add(".teddy/prompts")
    for name in _PROMPT_FILES:
        stem = name.rsplit(".", 1)[0]
        path = f".teddy/prompts/{stem}.xml"
        existing.add(path)
        contents[path] = f"<{stem}/>"

    return FakeFileSystem(existing, contents)


def main() -> None:
    fs = _build_fs()
    service = InitService(
        file_system=fs, config_dir=CONFIG_DIR, templates_dir=TEMPLATES_DIR
    )

    report = service.check_drift()
    print("edited_prompts :", report.edited_prompts)
    print("missing_prompts:", report.missing_prompts)

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _format_drift_clause,
    )

    clause = _format_drift_clause(
        "prompt",
        "prompts",
        ".teddy/prompts/",
        report.edited_prompts,
        report.missing_prompts,
    )
    print("message        :", clause)

    print()
    expected_differ = (
        len(report.edited_prompts) == len(_PROMPT_FILES)
        and not report.missing_prompts
    )
    if expected_differ:
        print("RESULT: PASS - same-stem .xml prompts reported as DIFFER")
    else:
        print("RESULT: FAIL - same-stem .xml prompts reported as MISSING")


if __name__ == "__main__":
    main()