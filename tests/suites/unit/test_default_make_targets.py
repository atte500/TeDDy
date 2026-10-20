"""Structural guard for the shipped Makefile's default targets.

The Makefile is the canonical entry point for the agent workflows, and it ships
in two byte-identical template copies that bootstrapped projects inherit. These
tests pin the contract the Windows portability fix established: target presence,
the POSIX shell preflight, the cmd-safe recipe surface, stderr diagnostics on
every blocking verdict, and template lockstep.
"""

from __future__ import annotations

import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MAKEFILE = _PROJECT_ROOT / "Makefile"
_PROJECT_TEMPLATE = _PROJECT_ROOT / "docs" / "templates" / "makefile.md"
_BUNDLED_TEMPLATE = (
    _PROJECT_ROOT / "src" / "teddy_executor" / "resources" / "templates" / "makefile.md"
)

_DEFAULT_TARGETS = ("commit", "push", "ci-watch", "probe", "logs", "test")
_POSIX_TARGETS = ("ci-watch", "probe", "logs")
_CMD_SAFE_TARGETS = ("commit", "push", "test")
_POSIX_ONLY_PROGRAMS = ("awk", "sed", "grep", "command -v", "sleep")

_BLOCKING_VERDICTS = (
    "is not a known commit",
    "is not on any remote branch",
    "no run registered",
    "unknown conclusion",
    "no run-bearing ancestor",
    "pinned base",
    "carries zero jobs",
    "YOUR regression",
)

_TARGET_RULE = re.compile(r"^(?P<name>[\w%-]+):(?:\s+(?P<prereqs>[^=]*))?$")


def _rule(target: str) -> tuple[list[str], list[str]]:
    """Collects every prerequisite and recipe line declared for one target.

    A target may span several lines, as ``probe`` and ``logs`` do: a
    target-specific variable, a prerequisite-only line, and the recipe line.
    Merging every declaration keeps assertions independent of that split.
    """
    lines = _MAKEFILE.read_text(encoding="utf-8").splitlines()
    prereqs: list[str] = []
    recipe: list[str] = []
    found = False
    for index, line in enumerate(lines):
        match = _TARGET_RULE.match(line)
        if match is None or match.group("name") != target:
            continue
        found = True
        prereqs.extend((match.group("prereqs") or "").split())
        for following in lines[index + 1 :]:
            if not following.startswith("\t"):
                break
            recipe.append(following)
    if not found:
        raise AssertionError(f"target {target!r} has no explicit rule")
    return prereqs, recipe


def test_every_default_target_is_declared_phony() -> None:
    phony = next(
        line
        for line in _MAKEFILE.read_text(encoding="utf-8").splitlines()
        if line.startswith(".PHONY:")
    ).split()
    for target in (*_DEFAULT_TARGETS, "_preflight"):
        assert target in phony, target


def test_every_default_target_declares_a_recipe() -> None:
    for target in _DEFAULT_TARGETS:
        _, recipe = _rule(target)
        assert recipe, target


def test_posix_targets_require_the_shell_preflight() -> None:
    for target in _POSIX_TARGETS:
        prereqs, _ = _rule(target)
        assert "_preflight" in prereqs, target


def test_preflight_verifies_every_tool_the_recipes_use() -> None:
    _, recipe = _rule("_preflight")
    body = "\n".join(recipe)
    for tool in ("git", "gh", "awk", "sed"):
        assert f"command -v {tool}" in body, tool


def test_preflight_confirms_the_windows_shell_is_git_bash() -> None:
    body = _MAKEFILE.read_text(encoding="utf-8")
    assert "SHELL_CHECK = uname -s" in body
    assert "MINGW|MSYS" in body


def test_cmd_safe_targets_avoid_posix_only_programs() -> None:
    for target in _CMD_SAFE_TARGETS:
        _, recipe = _rule(target)
        body = "\n".join(recipe)
        for program in _POSIX_ONLY_PROGRAMS:
            assert program not in body, (target, program)


def test_each_blocking_verdict_is_repeated_on_stderr() -> None:
    _, recipe = _rule("ci-watch")
    stderr_lines = [line for line in recipe if ">&2" in line]
    for verdict in _BLOCKING_VERDICTS:
        assert any(verdict in line for line in stderr_lines), verdict


def test_commit_runs_the_hooks_through_the_project_runner() -> None:
    _, recipe = _rule("commit")
    assert "-uv run pre-commit run" in [line.strip() for line in recipe]


def test_probe_passes_the_reason_with_portable_quoting() -> None:
    _, recipe = _rule("probe")
    body = "\n".join(recipe)
    assert '--field reason="$(REASON)"' in body
    assert "'$(REASON)'" not in body


def test_makefile_stays_ascii_only() -> None:
    text = _MAKEFILE.read_bytes()
    assert text.isascii(), (
        "Makefile text must stay ASCII so Windows consoles cannot mojibake it"
    )


def test_template_copies_are_byte_identical() -> None:
    assert _PROJECT_TEMPLATE.read_bytes() == _BUNDLED_TEMPLATE.read_bytes()


def test_templates_document_the_portability_contract() -> None:
    markers = (
        "_preflight",
        "uv run pre-commit run",
        '--field reason="$(REASON)"',
        ">&2",
    )
    for template in (_PROJECT_TEMPLATE, _BUNDLED_TEMPLATE):
        text = template.read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, (template.name, marker)
