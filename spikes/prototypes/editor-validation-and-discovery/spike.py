"""Empirical spike for Slice 03-01 Technical Key Unknowns.

KU1 - YamlConfigAdapter.set_setting() path handling for root_dir-based config
      paths (incl. directory creation) and in-memory cache freshness.
KU2 - _DIFF_FLAGS JetBrains bare "diff" flag convention when invoked through
      subprocess (argv must carry "diff" as a discrete element).
KU3 - TUI unknown-editor routing: current GUI before/after path vs the proposed
      annotated-diff path.

Run:
    uv run python spikes/prototypes/editor-validation-and-discovery/spike.py

Exit code 0 == all assertions passed (raw evidence printed to stdout).
"""
from __future__ import annotations

import asyncio
import os
import stat
import subprocess
import sys
import tempfile
from typing import Any, Optional

# --- make src/ importable when run directly -------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
_SRC = os.path.join(_REPO_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.adapters.inbound import textual_plan_reviewer_editor as ed

from set_setting_shadow import set_setting_shadow, set_setting_spec_proposed


# ---------------------------------------------------------------------------
# shared fakes
# ---------------------------------------------------------------------------
class StubEnv:
    """Minimal ISystemEnvironment double (spike-local)."""

    def __init__(self, which_map: Optional[dict] = None, env_map: Optional[dict] = None):
        self._which = which_map or {}
        self._env = env_map or {}

    def which(self, name: str) -> Optional[str]:
        return self._which.get(name)

    def get_env(self, key: str) -> Optional[str]:
        return self._env.get(key)


class StubConfig:
    """Minimal IConfigService double."""

    def __init__(self, settings: Optional[dict] = None):
        self._settings = settings or {}

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def get_config_path(self) -> str:
        return "<stub>"


def _make_fake_launcher(dirpath: str, name: str, capture_file: str) -> str:
    """Create an executable shell script that records its argv and exits 0."""
    path = os.path.join(dirpath, name)
    script = (
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" >> '{capture_file}'\n"
        "exit 0\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _read_lines(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


# ---------------------------------------------------------------------------
# KU1
# ---------------------------------------------------------------------------
def probe_ku1(results: list) -> None:
    print("\n" + "=" * 72)
    print("KU1  set_setting() path handling for root_dir-based config paths")
    print("=" * 72)

    tmp = tempfile.mkdtemp(prefix="ku1_root_")
    teddy_dir = os.path.join(tmp, ".teddy")
    expected_cfg = os.path.join(teddy_dir, "config.yaml")

    adapter = YamlConfigAdapter(root_dir=tmp)
    print(f"root_dir              = {tmp}")
    print(f"adapter._config_path  = {adapter._config_path}")
    print(f".teddy/ exists before = {os.path.exists(teddy_dir)}")
    assert adapter._config_path == expected_cfg, adapter._config_path
    assert not os.path.exists(teddy_dir), "precondition: .teddy must NOT exist"

    # A) spec-proposed write with the parent dir missing -> must fail
    print("\n[A] spec-proposed set_setting (no makedirs) with .teddy/ missing:")
    a_failed = False
    try:
        set_setting_spec_proposed(adapter._config_path, "editor", "nvim")
    except FileNotFoundError as exc:
        a_failed = True
        print(f"    -> FileNotFoundError: {exc}")
    print(f"    -> directory creation REQUIRED = {a_failed}")
    assert a_failed, "expected naive write to fail without parent dir"

    # B) after the dir exists, spec-proposed writes to disk but cache is stale
    print("\n[B] after mkdir, spec-proposed write -> disk OK but cache stale:")
    os.makedirs(teddy_dir, exist_ok=True)
    set_setting_spec_proposed(adapter._config_path, "editor", "nvim")
    on_disk = YamlConfigAdapter(root_dir=tmp).get_setting("editor")
    cached = adapter.get_setting("editor")
    print(f"    fresh-adapter read-back      = {on_disk!r}")
    print(f"    original adapter (cached)    = {cached!r}")
    assert on_disk == "nvim", on_disk
    assert cached != "nvim", "expected stale cache to prove cache-update gap"
    print("    -> cache update REQUIRED = True")

    # C) corrected shadow implementation
    print("\n[C] shadow set_setting (makedirs + cache update):")
    set_setting_shadow(adapter, "editor", "nvim")
    print(f"    adapter.get_setting('editor')= {adapter.get_setting('editor')!r}")
    assert adapter.get_setting("editor") == "nvim"
    fresh2 = YamlConfigAdapter(root_dir=tmp).get_setting("editor")
    print(f"    fresh-adapter read-back      = {fresh2!r}")
    assert fresh2 == "nvim"

    # D) dot-notation nested key + non-root_dir path
    print("\n[D] dot-notation value + non-root_dir (arbitrary nested) path:")
    set_setting_shadow(adapter, "diff_flags", ["--diff", "--wait"])
    assert adapter.get_setting("diff_flags") == ["--diff", "--wait"]
    print(f"    get_setting('diff_flags')     = {adapter.get_setting('diff_flags')!r}")

    tmp2 = tempfile.mkdtemp(prefix="ku1_plain_")
    plain_cfg = os.path.join(tmp2, "nested", "deep", "config.yaml")
    plain_adapter = YamlConfigAdapter(config_path=plain_cfg)
    print(f"    plain _config_path            = {plain_adapter._config_path}")
    assert plain_adapter._config_path == plain_cfg
    set_setting_shadow(plain_adapter, "editor", "hx")
    print(f"    created recursively           = {os.path.exists(plain_cfg)}")
    assert os.path.exists(plain_cfg)
    assert YamlConfigAdapter(config_path=plain_cfg).get_setting("editor") == "hx"

    results.extend([
        ("KU1 dir-creation required", a_failed),
        ("KU1 cache-update required", cached != "nvim"),
        ("KU1 shadow persists+reloads", fresh2 == "nvim"),
        ("KU1 nested/plain path", os.path.exists(plain_cfg)),
    ])


# ---------------------------------------------------------------------------
# KU2
# ---------------------------------------------------------------------------
def probe_ku2(results: list) -> None:
    print("\n" + "=" * 72)
    print('KU2  _DIFF_FLAGS JetBrains bare "diff" flag via subprocess')
    print("=" * 72)

    tmp = tempfile.mkdtemp(prefix="ku2_")
    f1 = os.path.join(tmp, "a.txt")
    f2 = os.path.join(tmp, "b.txt")
    with open(f1, "w", encoding="utf-8") as fh:
        fh.write("a\n")
    with open(f2, "w", encoding="utf-8") as fh:
        fh.write("b\n")

    # -- 1) the entry already present in the live table (idea) -------------
    idea_cap = os.path.join(tmp, "idea_cap.txt")
    fake_idea = _make_fake_launcher(tmp, "idea", idea_cap)
    helper = ConsoleToolingHelper(
        StubEnv(which_map={"idea": fake_idea}),
        StubConfig(settings={"editor": "idea"}),
    )
    cmd = helper.get_diff_viewer_command()
    print(f"\nidea: get_diff_viewer_command() = {cmd}")
    assert cmd == [fake_idea, "diff"], cmd
    subprocess.run(cmd + [f1, f2], check=True)
    argv = _read_lines(idea_cap)
    print(f"      launcher observed argv      = {argv}")
    assert argv == ["diff", f1, f2], argv

    # -- 2) the JetBrains entries the spec plans to add --------------------
    print("\nthe proposed JetBrains entries (simulated on the live table):")
    from teddy_executor.adapters.outbound.console_tooling import (
        ConsoleToolingHelper as CTH,
    )

    added = {
        "idea.sh": ["diff"],
        "webstorm": ["diff"],
        "phpstorm": ["diff"],
        "pycharm": ["diff"],
        "rubymine": ["diff"],
        "goland": ["diff"],
        "clion": ["diff"],
        "fleet": ["diff"],
    }
    snapshot = dict(CTH._DIFF_FLAGS)
    jetbrains_ok = True
    try:
        CTH._DIFF_FLAGS.update(added)
        for name in added:
            cap = os.path.join(tmp, f"{name}_cap.txt")
            fake = _make_fake_launcher(tmp, name, cap)
            h = ConsoleToolingHelper(
                StubEnv(which_map={name: fake}),
                StubConfig(settings={"editor": name}),
            )
            c = h.get_diff_viewer_command()
            subprocess.run(c + [f1, f2], check=True)
            got = _read_lines(cap)
            ok = c == [fake, "diff"] and got == ["diff", f1, f2]
            jetbrains_ok = jetbrains_ok and ok
            print(f"  {name:9s} -> {c!r:44s} argv={got} ok={ok}")
    finally:
        CTH._DIFF_FLAGS.clear()
        CTH._DIFF_FLAGS.update(snapshot)

    assert jetbrains_ok, "JetBrains bare 'diff' argv convention failed"
    results.extend([
        ("KU2 idea bare 'diff' argv", True),
        ("KU2 proposed JetBrains entries argv", jetbrains_ok),
    ])


# ---------------------------------------------------------------------------
# KU3
# ---------------------------------------------------------------------------
class _NullSuspend:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


class StubSystemEnv:
    def __init__(self, tmpdir: str):
        self.tmpdir = tmpdir
        self.create_temp_file_calls: list = []
        self.run_command_calls: list = []
        self.deleted: list = []

    def create_temp_file(self, suffix: str = ".txt") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.tmpdir)
        os.close(fd)
        self.create_temp_file_calls.append((suffix, path))
        return path

    def delete_file(self, path: str) -> None:
        self.deleted.append(str(path))

    def run_command(self, cmd, background: bool = False, **kwargs):
        self.run_command_calls.append({"cmd": list(cmd), "background": background})
        return None


class StubApp:
    def __init__(self, system_env: StubSystemEnv):
        self._system_env = system_env
        self.is_headless = True
        self.notifications: list = []
        self.suspend_count = 0

    def notify(self, message: str) -> None:
        self.notifications.append(message)

    def suspend(self):
        self.suspend_count += 1
        return _NullSuspend()

    async def push_screen_wait(self, screen):
        return True


class StubAction:
    def __init__(self, path: str, pending_temp_file: str):
        self.params = {"path": path}
        self.pending_temp_file = pending_temp_file
        self.modified = False
        self.modified_fields: list = []


async def probe_ku3(results: list) -> None:
    print("\n" + "=" * 72)
    print("KU3  TUI unknown-editor routing (GUI before/after vs annotated diff)")
    print("=" * 72)

    os.environ.pop("TEDDY_TEST_MOCK_EDITOR_OUTPUT", None)

    tmp = tempfile.mkdtemp(prefix="ku3_")
    fake_cli = _make_fake_launcher(tmp, "nvim", os.path.join(tmp, "cli_cap.txt"))
    fake_unknown = _make_fake_launcher(
        tmp, "my_editor", os.path.join(tmp, "unk_cap.txt")
    )

    original = "line1\nline2\n"
    proposed = "line1\nline2_changed\n"

    async def exercise(diff_viewer, label):
        env = StubSystemEnv(tmp)
        app = StubApp(env)
        pending = os.path.join(tmp, f"pending_{label}.py")
        with open(pending, "w", encoding="utf-8") as fh:
            fh.write(proposed)
        action = StubAction("some/file.py", pending)
        ok = await ed.preview_edit_diff_viewer(
            app, action, diff_viewer, original, proposed
        )
        annotated = not env.create_temp_file_calls and not env.run_command_calls
        gui = bool(env.run_command_calls)
        route = "ANNOTATED" if annotated else ("GUI" if gui else "UNKNOWN")
        print(
            f"  {label:16s} diff_viewer={diff_viewer}\n"
            f"      route={route:9s} suspends={app.suspend_count} "
            f"create_temp={len(env.create_temp_file_calls)} "
            f"run_command={len(env.run_command_calls)} ok={ok}"
        )
        return route

    print("\n[current src behavior]")
    r_cli = await exercise([fake_cli], "cli(nvim)")
    r_gui = await exercise(["code", "--diff"], "known_gui(code)")
    r_unk = await exercise([fake_unknown], "unknown(my_editor)")

    print("\n[proposed routing predicate]")
    from teddy_executor.adapters.outbound.console_tooling import (
        ConsoleToolingHelper as CTH,
    )

    def should_use_annotated(diff_viewer: list) -> bool:
        if ed._is_cli_editor(diff_viewer):
            return True
        basename = os.path.basename(diff_viewer[0]).lower()
        return basename not in CTH._DIFF_FLAGS

    p_cli = should_use_annotated([fake_cli])
    p_gui = should_use_annotated(["code", "--diff"])
    p_unk = should_use_annotated([fake_unknown])
    print(f"  cli(nvim)             -> annotated={p_cli}")
    print(f"  known_gui(code)       -> annotated={p_gui}")
    print(f"  unknown(my_editor)    -> annotated={p_unk}")

    assert r_cli == "ANNOTATED", "known CLI editor must take annotated path (baseline)"
    assert r_gui == "GUI", "known GUI editor must take GUI path (baseline)"
    assert r_unk == "GUI", "CURRENT behavior: unknown editor takes GUI path (the gap)"
    assert p_cli is True and p_gui is False and p_unk is True, (p_cli, p_gui, p_unk)

    results.extend([
        ("KU3 baseline cli->annotated", r_cli == "ANNOTATED"),
        ("KU3 baseline known gui->GUI", r_gui == "GUI"),
        ("KU3 baseline unknown->GUI (gap confirmed)", r_unk == "GUI"),
        ("KU3 proposed predicate routes unknown->annotated", p_unk is True),
    ])


def main() -> int:
    results: list = []
    probe_ku1(results)
    probe_ku2(results)
    asyncio.run(probe_ku3(results))

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failures = [n for n, ok in results if not ok]
    if failures:
        print(f"\nFAILED: {failures}")
        return 1
    print("\nAll probe assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())