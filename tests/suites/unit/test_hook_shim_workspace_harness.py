"""Harness self-tests for the HookShimWorkspace test double.

The fake models the .git/hooks filesystem state validated by the
prototype (spikes/prototypes/windows-startup-latency/
validate_shim_determinism.py, ALL PASS):

- ONE shim per hook type under <root>/.git/hooks/, each declaring only
  its OWN --hook-type=<type> (per-shim guard semantics)
- Each valid shim: contains "hook-impl", declares
  "--config=.pre-commit-config.yaml", declares its own
  "--hook-type=<type>", and embeds an INSTALL_PYTHON path that exists
- Fallback triggers modeled as explicit per-shim mutations: missing
  shim, dead interpreter, foreign content, mismatched hook type,
  missing config flag

State is backed by REAL files in a temp directory because the skip
guard under test reads real files; dynamic mock objects would not
exercise the actual file semantics (anti-mock-poisoning: state is
faked with real files, not mocks).
"""

from pathlib import Path

import pytest

from tests.harness.setup.hook_shims import HookShimWorkspace

EXPECTED_HOOK_TYPES = ("pre-commit", "post-commit")
CONFIG_FLAG = "--config=.pre-commit-config.yaml"


@pytest.fixture
def workspace():
    with HookShimWorkspace() as fake:
        yield fake


class TestShimLayout:
    """The hooks directory layout matches git's default anatomy."""

    def test_hooks_dir_is_under_git_dir(self, workspace):
        assert workspace.hooks_dir == workspace.root / ".git" / "hooks"

    def test_hooks_dir_exists_on_construction(self, workspace):
        assert workspace.hooks_dir.is_dir()

    def test_shim_path_locates_shim_per_hook_type(self, workspace):
        for hook_type in EXPECTED_HOOK_TYPES:
            assert workspace.shim_path(hook_type) == (workspace.hooks_dir / hook_type)


class TestValidShims:
    """Valid shims carry every property the skip guard checks."""

    def test_write_valid_shims_creates_shim_per_hook_type(self, workspace):
        workspace.write_valid_shims()

        for hook_type in EXPECTED_HOOK_TYPES:
            assert workspace.shim_path(hook_type).exists()

    @pytest.mark.parametrize("hook_type", EXPECTED_HOOK_TYPES)
    def test_shim_declares_only_its_own_hook_type(self, workspace, hook_type):
        workspace.write_valid_shims()

        content = workspace.read_shim(hook_type)
        assert f"--hook-type={hook_type}" in content
        # Per-shim independence: the OTHER hook type is not declared here
        other = next(t for t in EXPECTED_HOOK_TYPES if t != hook_type)
        assert f"--hook-type={other}" not in content

    @pytest.mark.parametrize("hook_type", EXPECTED_HOOK_TYPES)
    def test_shim_declares_config_flag(self, workspace, hook_type):
        workspace.write_valid_shims()

        assert CONFIG_FLAG in workspace.read_shim(hook_type)

    @pytest.mark.parametrize("hook_type", EXPECTED_HOOK_TYPES)
    def test_shim_contains_hook_impl(self, workspace, hook_type):
        workspace.write_valid_shims()

        assert "hook-impl" in workspace.read_shim(hook_type)

    @pytest.mark.parametrize("hook_type", EXPECTED_HOOK_TYPES)
    def test_shim_embeds_existing_interpreter(self, workspace, hook_type):
        workspace.write_valid_shims()

        content = workspace.read_shim(hook_type)
        install_python = content.split("INSTALL_PYTHON=")[1].splitlines()[0].strip()
        assert Path(install_python).exists()

    def test_write_valid_shims_accepts_custom_interpreter(self, workspace):
        custom = workspace.root / "venv" / "bin" / "python"
        custom.parent.mkdir(parents=True)
        custom.write_text("", encoding="utf-8")

        workspace.write_valid_shims(install_python=str(custom))

        for hook_type in EXPECTED_HOOK_TYPES:
            content = workspace.read_shim(hook_type)
            assert f"INSTALL_PYTHON={custom}" in content


class TestFallbackTriggerMutations:
    """Each mutation breaks exactly one guard property (per shim)."""

    def test_remove_shim_makes_shim_missing(self, workspace):
        workspace.write_valid_shims()

        workspace.remove_shim("pre-commit")

        assert not workspace.shim_path("pre-commit").exists()

    def test_kill_interpreter_points_at_dead_path(self, workspace):
        workspace.write_valid_shims()

        workspace.kill_interpreter("pre-commit")

        content = workspace.read_shim("pre-commit")
        install_python = content.split("INSTALL_PYTHON=")[1].splitlines()[0].strip()
        assert not Path(install_python).exists()

    def test_write_foreign_shim_removes_precommit_properties(self, workspace):
        workspace.write_valid_shims()

        workspace.write_foreign_shim("pre-commit")

        content = workspace.read_shim("pre-commit")
        assert "hook-impl" not in content

    def test_mismatch_hook_type_declares_foreign_type(self, workspace):
        workspace.write_valid_shims()

        workspace.mismatch_hook_type("pre-commit")

        content = workspace.read_shim("pre-commit")
        assert "--hook-type=pre-commit" not in content
        assert "--hook-type=post-commit" in content

    def test_drop_config_flag_removes_config_declaration(self, workspace):
        workspace.write_valid_shims()

        workspace.drop_config_flag("pre-commit")

        assert CONFIG_FLAG not in workspace.read_shim("pre-commit")

    def test_mutations_are_isolated_per_shim(self, workspace):
        """Corrupting one shim must leave the other shim fully valid
        (the guard is PER SHIM — each shim declares only its own type)."""
        workspace.write_valid_shims()

        workspace.kill_interpreter("pre-commit")

        other_content = workspace.read_shim("post-commit")
        assert "--hook-type=post-commit" in other_content
        assert CONFIG_FLAG in other_content
        assert "hook-impl" in other_content
        install_python = (
            other_content.split("INSTALL_PYTHON=")[1].splitlines()[0].strip()
        )
        assert Path(install_python).exists()


class TestCleanup:
    """The fake must leave no filesystem residue behind."""

    def test_context_manager_removes_temp_root(self):
        with HookShimWorkspace() as fake:
            root = fake.root
            assert root.is_dir()

        assert not root.exists()
