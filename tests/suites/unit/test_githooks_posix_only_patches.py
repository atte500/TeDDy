"""Unit tests for the POSIX-only patch poka-yoke hook.

Verifies ``.githooks/check_posix_only_patches.py`` flags tests that monkeypatch a
POSIX-only symbol (e.g. ``os.killpg``) without a platform guard, and accepts the
established guard / opt-out idioms. Guards against the Bug-61 class of
windows-latest CI failures.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_HOOK_PATH = (
    Path(__file__).resolve().parents[3] / ".githooks" / "check_posix_only_patches.py"
)


def _load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_posix_only_patches", _HOOK_PATH
    )
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


def test_flags_unguarded_posix_patch(hook: Any, tmp_path: Path) -> None:
    # Mirrors the original Bug-61 defect: an unguarded os.killpg monkeypatch.
    source = (
        "import os\n"
        "import signal\n"
        "\n"
        "def test_await_process_terminates_group(monkeypatch):\n"
        "    killed = []\n"
        "    monkeypatch.setattr(os, 'killpg', lambda pid, sig: None)\n"
        "    assert killed == []\n"
    )
    violations = hook.check_file(_write(tmp_path, source))
    assert violations
    assert "killpg" in violations[0]


def test_allows_in_body_windows_skip_guard(hook: Any, tmp_path: Path) -> None:
    source = (
        "import os\n"
        "import sys\n"
        "import pytest\n"
        "\n"
        "def test_x(monkeypatch):\n"
        "    if sys.platform == 'win32':\n"
        "        pytest.skip('killpg is POSIX only')\n"
        "    monkeypatch.setattr(os, 'killpg', lambda pid, sig: None)\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_skipif_decorator(hook: Any, tmp_path: Path) -> None:
    source = (
        "import os\n"
        "import sys\n"
        "import pytest\n"
        "\n"
        "@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX only')\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(os, 'killpg', lambda pid, sig: None)\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_raising_false_optout(hook: Any, tmp_path: Path) -> None:
    source = (
        "import os\n"
        "\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(os, 'killpg', lambda pid, sig: None, raising=False)\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_patch_create_true_optout(hook: Any, tmp_path: Path) -> None:
    source = (
        "from unittest.mock import patch\n"
        "\n"
        "def test_x():\n"
        "    with patch('os.killpg', create=True):\n"
        "        pass\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_getattr_existence_guard(hook: Any, tmp_path: Path) -> None:
    # Mirrors tests/harness/setup/composition.py's guard_os_killpg fixture.
    source = (
        "import os\n"
        "\n"
        "def test_x(monkeypatch):\n"
        "    original = getattr(os, 'killpg', None)\n"
        "    if original:\n"
        "        monkeypatch.setattr(os, 'killpg', original)\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []


def test_allows_windows_safe_os_kill_patch(hook: Any, tmp_path: Path) -> None:
    # os.kill exists on Windows -> not part of the POSIX-only class.
    source = (
        "import os\n"
        "\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(os, 'kill', lambda pid, sig: None)\n"
    )
    assert hook.check_file(_write(tmp_path, source)) == []
