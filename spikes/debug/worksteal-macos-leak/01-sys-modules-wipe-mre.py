"""Reproduce the sys.modules wipe that hides a terminal patch from a later test.

The macOS CI failure asserts that ``tcflush`` was called zero times after the
tty-guards fixture replaced ``sys.modules``. That fixture deletes the terminal
entry and then enters ``patch.dict``, which snapshots the already-wiped mapping.
This probe reproduces the same pattern with a synthetic terminal module, so the
mechanism is observable on any host, and repeats it with ``monkeypatch.setitem``
to show that the isolate-and-restore form repairs the patch target.
"""

import importlib
import sys
import types
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import MagicMock, patch

from _pytest.monkeypatch import MonkeyPatch

MODULE_NAME = "teddy_probe_tty"
SOURCE = "def tcflush(fd, when):\n    return None\n"


def prepare() -> Path:
    """Write the synthetic terminal module and put it on the import path."""
    root = Path(mkdtemp(prefix="teddy-sys-modules-probe-"))
    (root / f"{MODULE_NAME}.py").write_text(SOURCE, encoding="utf-8")
    sys.path.insert(0, str(root))
    return root


def fresh_module() -> types.ModuleType:
    """Import a clean instance of the synthetic terminal module."""
    sys.modules.pop(MODULE_NAME, None)
    return importlib.import_module(MODULE_NAME)


def subject_flush() -> None:
    """Mirror the adapter: a function-local import followed by the call."""
    import teddy_probe_tty

    teddy_probe_tty.tcflush(sys.stdin, 0)


def leak_scenario() -> int:
    """Reproduce the delete-then-patch pattern and report the spy count."""
    bound = fresh_module()
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]

    fake = types.ModuleType(MODULE_NAME)
    with patch.dict("sys.modules", {MODULE_NAME: fake}):
        installed = sys.modules.get(MODULE_NAME) is fake
    print("leak: fake installed inside patch.dict:", installed)
    print("leak: entry present after patch.dict exit:", MODULE_NAME in sys.modules)

    spy = MagicMock()
    bound.tcflush = spy
    subject_flush()
    resolved = sys.modules.get(MODULE_NAME)
    print("leak: adapter imported the victim's bound object:", resolved is bound)
    print("leak: spy call count:", spy.call_count)
    return spy.call_count


def isolated_scenario() -> int:
    """Repeat the pattern with setitem restore semantics and report the count."""
    bound = fresh_module()
    fake = types.ModuleType(MODULE_NAME)

    monkeypatch = MonkeyPatch()
    monkeypatch.setitem(sys.modules, MODULE_NAME, fake)
    installed = sys.modules.get(MODULE_NAME) is fake
    monkeypatch.undo()
    restored = sys.modules.get(MODULE_NAME) is bound
    print("isolated: fake installed inside setitem:", installed)
    print("isolated: entry restored to the bound object on undo:", restored)

    spy = MagicMock()
    bound.tcflush = spy
    subject_flush()
    print("isolated: spy call count:", spy.call_count)
    return spy.call_count


def main() -> None:
    prepare()
    leaked = leak_scenario()
    isolated = isolated_scenario()
    print()
    print("reproduced the zero-call failure:", leaked == 0)
    print("setitem repairs the patch target:", isolated == 1)


if __name__ == "__main__":
    main()