"""Fake .git/hooks shim filesystem state for the pre-commit skip guard.

The fake models the shim filesystem state validated by the prototype
(spikes/prototypes/windows-startup-latency/validate_shim_determinism.py,
ALL PASS):

- ONE shim per hook type under <root>/.git/hooks/, each declaring only
  its OWN --hook-type=<type> (per-shim guard semantics)
- Each valid shim: contains "hook-impl", declares
  "--config=.pre-commit-config.yaml", declares its own
  "--hook-type=<type>", and embeds an INSTALL_PYTHON path that exists
- Fallback triggers modeled as explicit per-shim mutations: missing
  shim, dead interpreter, foreign content, mismatched hook type,
  missing config flag

State is backed by REAL files in a temp directory (tempfile.mkdtemp per
the architecture's temp-file standard) because the skip guard under
test reads real files; dynamic mock objects would not exercise the
actual file semantics (anti-mock-poisoning: state is faked with real
files, not mocks).
"""

import shutil
import sys
import tempfile
from pathlib import Path

CONFIG_FLAG = "--config=.pre-commit-config.yaml"
DEFAULT_HOOK_TYPES = ("pre-commit", "post-commit")
DEAD_INTERPRETER = "/nonexistent/teddy-dead-interpreter/python"
FOREIGN_CONTENT = "#!/bin/sh\necho not-pre-commit\n"


class HookShimWorkspace:
    """File-state fake for the .git/hooks shim layout.

    Context-manager usage guarantees zero filesystem residue: the temp
    root is removed on exit.
    """

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="teddy-fake-hook-shims-"))
        self.hooks_dir = self.root / ".git" / "hooks"
        self.hooks_dir.mkdir(parents=True)

    def __enter__(self) -> "HookShimWorkspace":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def shim_path(self, hook_type: str) -> Path:
        """Returns the shim path for a hook type (git's default anatomy)."""
        return self.hooks_dir / hook_type

    def write_valid_shims(
        self,
        hook_types: tuple[str, ...] = DEFAULT_HOOK_TYPES,
        install_python: str | None = None,
    ) -> None:
        """Writes one valid shim per hook type.

        install_python defaults to the current interpreter (a path that
        exists on disk); pass an explicit path to model install-method
        variance (pipx/uv/pip differ only in the interpreter path).
        """
        interpreter = install_python if install_python is not None else sys.executable
        for hook_type in hook_types:
            self.shim_path(hook_type).write_text(
                self._shim_content(hook_type, interpreter), encoding="utf-8"
            )

    def read_shim(self, hook_type: str) -> str:
        """Reads the raw shim content for a hook type."""
        return self.shim_path(hook_type).read_text(encoding="utf-8")

    # --- Fallback-trigger mutations (each scoped to exactly ONE shim) ---

    def remove_shim(self, hook_type: str) -> None:
        """Deletes the shim (missing-shim fallback trigger)."""
        self.shim_path(hook_type).unlink(missing_ok=True)

    def kill_interpreter(self, hook_type: str) -> None:
        """Rewrites the INSTALL_PYTHON line to a dead path
        (dead-interpreter fallback trigger)."""
        content = self.read_shim(hook_type)
        lines = content.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.startswith("INSTALL_PYTHON="):
                lines[index] = f"INSTALL_PYTHON={DEAD_INTERPRETER}\n"
                break
        self.shim_path(hook_type).write_text("".join(lines), encoding="utf-8")

    def write_foreign_shim(self, hook_type: str) -> None:
        """Overwrites the shim with non-pre-commit content
        (foreign-content fallback trigger)."""
        self.shim_path(hook_type).write_text(FOREIGN_CONTENT, encoding="utf-8")

    def mismatch_hook_type(self, hook_type: str) -> None:
        """Rewrites the shim as a valid shim for a DIFFERENT hook type
        (hook-type-mismatch fallback trigger: the shim was installed by
        another configuration declaring its own --hook-type=)."""
        other = next((t for t in DEFAULT_HOOK_TYPES if t != hook_type), "pre-commit")
        self.shim_path(hook_type).write_text(
            self._shim_content(other, sys.executable), encoding="utf-8"
        )

    def drop_config_flag(self, hook_type: str) -> None:
        """Removes only the --config= declaration, keeping all other
        shim properties intact (missing-config-flag fallback trigger)."""
        content = self.read_shim(hook_type)
        self.shim_path(hook_type).write_text(
            content.replace(CONFIG_FLAG, ""), encoding="utf-8"
        )

    def _shim_content(self, hook_type: str, install_python: str) -> str:
        return (
            "#!/usr/bin/env bash\n"
            f"INSTALL_PYTHON={install_python}\n"
            f"ARGS=(hook-impl {CONFIG_FLAG} --hook-type={hook_type})\n"
        )
