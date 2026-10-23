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

_DEFAULT_TARGETS = ("commit", "push", "ci-watch", "probe", "logs", "test", "help")
_POSIX_TARGETS = ("ci-watch", "probe", "logs")
_CMD_SAFE_TARGETS = ("commit", "push", "test")
_POSIX_ONLY_PROGRAMS = ("awk", "sed", "grep", "command -v", "sleep")

_BASH_ONLY_PROGRAMS = (
    "sleep",
    "echo",
    "awk",
    "sed",
    "grep",
    "cat",
    "printf",
    "sort",
    "tail",
    "head",
)

_SHELL_METACHARACTERS = (
    "$",
    ";",
    "&",
    "|",
    "<",
    ">",
    "(",
    ")",
    "{",
    "}",
    '"',
    "'",
    "`",
    "\\",
)

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

    A target may declare its prerequisites on a line separate from its recipe.
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


def test_advisory_hook_pass_reports_its_outcome_in_plain_language() -> None:
    _, recipe = _rule("commit")
    body = "\n".join(recipe)
    assert "uv run pre-commit run || echo" in body, (
        "the advisory pass must consume its own exit code"
    )
    assert not any(line.strip().startswith("-uv run") for line in recipe), (
        "the ignore marker prints a bare error line that reads as a defect"
    )


def test_make_prints_help_when_it_runs_without_a_goal() -> None:
    body = _MAKEFILE.read_text(encoding="utf-8")
    assert ".DEFAULT_GOAL := help" in body


def test_command_line_words_must_be_known_targets() -> None:
    body = _MAKEFILE.read_text(encoding="utf-8")
    assert "_KNOWN_GOALS :=" in body
    assert "$(filter-out $(_KNOWN_GOALS),$(MAKECMDGOALS))" in body
    assert "Unknown target" in body


def test_required_values_are_enforced_at_parse_time() -> None:
    body = _MAKEFILE.read_text(encoding="utf-8")
    for target, variable in (("commit", "MSG"), ("probe", "REASON"), ("logs", "RUN")):
        assert f"$(filter {target},$(MAKECMDGOALS))" in body, target
        _, recipe = _rule(target)
        assert f"$({variable})" in "\n".join(recipe), target
        assert not any("$(error Usage" in line for line in recipe), target


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
        "spawns a recipe line directly",
    )
    for template in (_PROJECT_TEMPLATE, _BUNDLED_TEMPLATE):
        text = template.read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, (template.name, marker)


def _logical_recipe_lines(recipe: list[str]) -> list[str]:
    """Joins physical recipe lines that continue with a trailing backslash.

    Make routes a logical line through the recipe shell when it carries a
    metacharacter, so the routing decision must be checked after folding.
    """
    logical: list[str] = []
    buffer = ""
    for line in recipe:
        body = line[1:] if line.startswith("\t") else line
        if body.endswith("\\"):
            buffer += body[:-1]
            continue
        buffer += body
        logical.append(buffer)
        buffer = ""
    if buffer:
        logical.append(buffer)
    return logical


def test_bash_only_programs_are_routed_through_the_recipe_shell() -> None:
    """A metacharacter-free line is spawned directly and bypasses SHELL.

    On Windows that direct spawn fails for Git Bash-only programs such as
    sleep and for shell builtins such as echo.
    """
    for target in _POSIX_TARGETS:
        _, recipe = _rule(target)
        for line in _logical_recipe_lines(recipe):
            words = line.lstrip("@-+").split()
            if not words or words[0] not in _BASH_ONLY_PROGRAMS:
                continue
            assert any(marker in line for marker in _SHELL_METACHARACTERS), (
                f"{target} spawns {words[0]!r} directly, which bypasses SHELL"
            )


def test_probe_resolves_its_run_by_the_pushed_sha() -> None:
    _, recipe = _rule("probe")
    body = "\n".join(recipe)
    assert "gh run list --workflow debug.yml" in body
    assert "headSha" in body
    assert "select(.headSha" in body
    assert "$$SHA" in body


def test_probe_reports_an_unregistered_run_on_stderr() -> None:
    _, recipe = _rule("probe")
    stderr_lines = [line for line in recipe if ">&2" in line]
    assert any("no run registered" in line for line in stderr_lines)


_DOCUMENTED_SURFACES = (
    _MAKEFILE,
    _PROJECT_TEMPLATE,
    _BUNDLED_TEMPLATE,
    _PROJECT_ROOT / "src" / "teddy_executor" / "resources" / "MRP.md",
    *sorted(
        (
            _PROJECT_ROOT
            / "src"
            / "teddy_executor"
            / "resources"
            / "config"
            / "prompts"
        ).glob("*.md")
    ),
)

_POSITIONAL_INVOCATIONS = (
    re.compile(r"make commit [\"']"),
    re.compile(r"make probe [\"']"),
    re.compile(r"make logs <"),
    re.compile(r"make logs \$\$"),
)


def test_documented_invocations_use_named_variables() -> None:
    """A positional call aborts at parse time, so no document may teach one."""
    for path in _DOCUMENTED_SURFACES:
        text = path.read_text(encoding="utf-8")
        for pattern in _POSITIONAL_INVOCATIONS:
            match = pattern.search(text)
            assert match is None, f"{path.name} still teaches {match.group(0)!r}"
