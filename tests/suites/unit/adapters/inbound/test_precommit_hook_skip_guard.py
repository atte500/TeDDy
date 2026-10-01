"""Unit tests for the pre-commit hook compare-and-skip guard.

The guard in `_ensure_commit_hooks` must skip the `pre-commit install`
subprocess when every requested hook shim is already current (per-shim
property check validated by the prototype:
spikes/prototypes/windows-startup-latency/validate_shim_determinism.py,
ALL PASS) and fall back to the real install on ANY mismatch — safety is
never reduced.

The filesystem dimension is driven by HookShimWorkspace (real temp
files). The install spawn is observed by a def-based recording double
that intercepts ONLY the install argv and delegates every other command
(the hooks-dir resolver's git rev-parse) to the real subprocess.run
captured before the patch, so the guard exercises real git resolution
inside a real temp repository.
"""

import subprocess

import pytest

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _ensure_commit_hooks,
)
from tests.harness.setup.hook_shims import HookShimWorkspace

INSTALL_ARGV = [
    "pre-commit",
    "install",
    "-f",
    "-t",
    "pre-commit",
    "-t",
    "post-commit",
]
GREEN_NOTIFICATION = "pre-commit hooks installed"
FALLBACK_MUTATIONS = (
    "remove_shim",
    "kill_interpreter",
    "write_foreign_shim",
    "mismatch_hook_type",
    "drop_config_flag",
)


class InstallSpawnRecorder:
    """Def-based recording double for subprocess.run.

    Records `pre-commit install` spawns (returning a successful
    CompletedProcess for them) and delegates every other command — the
    hooks-dir resolver's `git rev-parse` — to the REAL subprocess.run
    captured before the patch, so git resolution runs for real inside
    the temp repository.
    """

    def __init__(self, real_run) -> None:
        self._real_run = real_run
        self.install_calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        if cmd[:2] == ["pre-commit", "install"]:
            self.install_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, returncode=0)
        return self._real_run(cmd, **kwargs)


@pytest.fixture
def workspace():
    with HookShimWorkspace() as fake:
        yield fake


@pytest.fixture
def recorder(monkeypatch):
    real_run = subprocess.run
    recorder = InstallSpawnRecorder(real_run)
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.subprocess.run",
        recorder,
    )
    return recorder


@pytest.fixture
def pre_commit_cli(monkeypatch):
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.shutil.which",
        lambda name: "/fake/pre-commit" if name == "pre-commit" else None,
    )


@pytest.fixture
def hook_repo(workspace, monkeypatch):
    """A real git repository with valid shims and a config stub at CWD."""
    workspace.write_valid_shims()
    subprocess.run(
        ["git", "init", "-q"],
        cwd=workspace.root,
        check=True,
        capture_output=True,
    )
    (workspace.root / ".pre-commit-config.yaml").write_text(
        "repos: []\n", encoding="utf-8"
    )
    monkeypatch.chdir(workspace.root)
    return workspace


class TestSkipPath:
    """Valid shims => NO install spawn; the green notification still shows."""

    def test_valid_shims_skip_the_install_spawn(
        self, hook_repo, recorder, pre_commit_cli, capsys
    ):
        _ensure_commit_hooks()

        assert recorder.install_calls == []
        assert GREEN_NOTIFICATION in capsys.readouterr().err

    def test_alternate_install_method_interpreter_still_skips(
        self, hook_repo, recorder, pre_commit_cli
    ):
        custom_interpreter = hook_repo.root / "venv" / "bin" / "python"
        custom_interpreter.parent.mkdir(parents=True)
        custom_interpreter.write_text("", encoding="utf-8")
        hook_repo.write_valid_shims(install_python=str(custom_interpreter))

        _ensure_commit_hooks()

        assert recorder.install_calls == []

    def test_custom_hooks_path_is_resolved_for_the_skip(
        self, hook_repo, recorder, pre_commit_cli
    ):
        custom_hooks_dir = hook_repo.root / "custom-hooks"
        hook_repo.hooks_dir.rename(custom_hooks_dir)
        subprocess.run(
            ["git", "config", "core.hooksPath", "custom-hooks"],
            cwd=hook_repo.root,
            check=True,
            capture_output=True,
        )

        _ensure_commit_hooks()

        assert recorder.install_calls == []


class TestFallbackTriggers:
    """ANY per-shim mismatch => the real install spawn with verbatim argv."""

    @pytest.mark.parametrize("mutation", FALLBACK_MUTATIONS)
    def test_broken_pre_commit_shim_falls_back_to_install(
        self, hook_repo, recorder, pre_commit_cli, mutation
    ):
        getattr(hook_repo, mutation)("pre-commit")

        _ensure_commit_hooks()

        assert recorder.install_calls == [INSTALL_ARGV]

    def test_broken_post_commit_shim_falls_back_to_install(
        self, hook_repo, recorder, pre_commit_cli
    ):
        hook_repo.kill_interpreter("post-commit")

        _ensure_commit_hooks()

        assert recorder.install_calls == [INSTALL_ARGV]

    def test_unresolvable_hooks_dir_falls_back_to_install(
        self, workspace, recorder, pre_commit_cli, monkeypatch
    ):
        workspace.write_valid_shims()
        (workspace.root / ".pre-commit-config.yaml").write_text(
            "repos: []\n", encoding="utf-8"
        )
        monkeypatch.chdir(workspace.root)  # NOT a git repository

        _ensure_commit_hooks()

        assert recorder.install_calls == [INSTALL_ARGV]
