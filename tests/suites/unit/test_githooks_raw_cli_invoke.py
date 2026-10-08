"""Unit tests for the raw side-effecting CLI invoke poka-yoke hook.

Verifies ``.githooks/check_raw_cli_invoke.py`` flags tests that drive a
side-effecting CLI command (``init``/``start``/``resume``/``execute``/
``context``) without CWD isolation, and accepts the established isolation and
opt-out idioms. Guards against the repo-root pollution class (the macOS-CI
``docs/templates/`` leak).
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_HOOK_PATH = (
    Path(__file__).resolve().parents[3] / ".githooks" / "check_raw_cli_invoke.py"
)


def _load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_raw_cli_invoke", _HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook() -> Any:
    return _load_hook()


def _write(tmp_path: Path, body: str) -> str:
    path = tmp_path / "sample.py"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_flags_unguarded_bare_init(hook: Any, tmp_path: Path) -> None:
    # Mirrors the original defect: bare-init invoked without a CWD change.
    source = (
        "from typer.testing import CliRunner\n"
        "from teddy_executor.__main__ import app\n"
        "\n"
        "def test_init_calls_prewarm(monkeypatch):\n"
        "    runner = CliRunner()\n"
        "    result = runner.invoke(app, ['init'])\n"
        "    assert result.exit_code == 0\n"
    )
    violations = hook.check_file(_write(tmp_path, source))
    assert violations
    assert "init" in source and "side-effecting" in violations[0]


def test_allows_chdir_guarded_invoke(hook: Any, tmp_path: Path) -> None:
    source = (
        "from typer.testing import CliRunner\n"
        "from teddy_executor.__main__ import app\n"
        "\n"
        "def test_init_isolated(tmp_path, monkeypatch):\n"
        "    monkeypatch.chdir(tmp_path)\n"
        "    result = CliRunner().invoke(app, ['init'])\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_help_only_invoke(hook: Any, tmp_path: Path) -> None:
    source = (
        "from typer.testing import CliRunner\n"
        "from teddy_executor.__main__ import app\n"
        "\n"
        "def test_resume_help():\n"
        "    result = CliRunner().invoke(app, ['resume', '--help'])\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_non_side_effecting_command(hook: Any, tmp_path: Path) -> None:
    source = (
        "from typer.testing import CliRunner\n"
        "from teddy_executor.__main__ import app\n"
        "\n"
        "def test_version():\n"
        "    result = CliRunner().invoke(app, ['version'])\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_dynamic_args(hook: Any, tmp_path: Path) -> None:
    source = (
        "from typer.testing import CliRunner\n"
        "from teddy_executor.__main__ import app\n"
        "\n"
        "def test_run(args):\n"
        "    result = CliRunner().invoke(app, args)\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_explicit_optout(hook: Any, tmp_path: Path) -> None:
    source = (
        "from typer.testing import CliRunner\n"
        "from teddy_executor.__main__ import app\n"
        "\n"
        "def test_context_deliberate():\n"
        "    # raw-cli-invoke-ok: reads only, no repo-root writes\n"
        "    result = CliRunner().invoke(app, ['context', '--no-copy'])\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []
