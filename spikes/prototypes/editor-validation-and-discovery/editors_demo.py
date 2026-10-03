"""Interactive demo for the Slice 03-01 console editor-selection UI.

This is a PROTOTYPE (spike-local). It renders the candidate preflight
editor-selection block exactly as a user would see it, with adjustable knobs,
so the *[Functional]* Key Unknown ("Console editor-selection UI") can be tuned
before the Developer implements ``_validate_editor_config`` /
``_prompt_for_editor_selection`` / ``_prompt_for_custom_editor``.

It imports nothing from ``src/`` (the ``discover_editors`` method does not exist
yet); discovery is simulated via ``--editors``. It mirrors the codebase's
``typer`` console conventions (``typer.secho(fg=..., err=True)``) so the look is
faithful.

Interactive (tune the look):

    uv run python spikes/prototypes/editor-validation-and-discovery/editors_demo.py

Scripted / non-TTY (feed canned inputs; empty segment == Enter):

    uv run python spikes/prototypes/editor-validation-and-discovery/editors_demo.py \\
        --inputs "1,bad,2,"

Self-verifying battery:

    uv run python spikes/prototypes/editor-validation-and-discovery/editors_demo.py --selftest
"""
from __future__ import annotations

import argparse
import shutil
import sys
from typing import Optional

import typer

# --- Fixed strings pinned by the spec (section 4) --------------------------
WARN_MISSING = (
    "\u26a0 Configured editor '{editor}' not found in PATH. Discovering alternatives..."
)
MSG_UNCONFIGURED = "No editor configured. Scanning for available editors in PATH..."
FALLBACK_CUSTOM = "Or type a custom editor command (leave empty to disable):"
NO_KNOWN = (
    "No known editors found. Enter a custom editor command (leave empty to disable):"
)
SAVED = "Editor preference saved to .teddy/config.yaml."

# A plausible, deterministic discovery set (name, resolved path).
DEFAULT_DISCOVERED: list[tuple[str, str]] = [
    ("nvim", "/usr/local/bin/nvim"),
    ("vim", "/usr/bin/vim"),
    ("code", "/usr/local/bin/code"),
    ("cursor", "/Applications/Cursor.app/Contents/MacOS/cursor"),
    ("zed", "/usr/local/bin/zed"),
    ("nano", "/usr/bin/nano"),
]

# The spec only pins the *fallback* prompt string. This is a candidate primary
# prompt; "{n}" expands to the number of discovered editors.
DEFAULT_PRIMARY_PROMPT = (
    "Select an editor [1-{n}] (number, custom command, or empty to disable): "
)


class Emitter:
    """Routes output to typer, or captures it (for the self-test)."""

    def __init__(self, color: bool, capture: Optional[list[str]] = None):
        self.color = color
        self.capture = capture

    def __call__(
        self,
        text: str = "",
        fg: Optional[str] = None,
        bold: bool = False,
        err: bool = True,
    ) -> None:
        if self.capture is not None:
            self.capture.append(text)
            return
        if fg and self.color:
            typer.secho(text, fg=getattr(typer.colors, fg.upper()), bold=bold, err=err)
        else:
            typer.echo(text, err=err)


class InputFeeder:
    """Reads from typer.prompt (interactive) or a scripted input list."""

    def __init__(self, script: Optional[list[str]], emitter: Emitter):
        self._script = script
        self._i = 0
        self._emitter = emitter

    def prompt(self, text: str) -> str:
        if self._script is not None:
            if self._i >= len(self._script):
                self._emitter(f"{text}<EOF>")
                raise EOFError
            value = self._script[self._i]
            self._i += 1
            self._emitter(f"{text}{value}")
            return value
        try:
            return typer.prompt(text, default="", show_default=False, err=True)
        except (Exception, KeyboardInterrupt) as exc:
            # click raises Abort (a RuntimeError) on Ctrl-D/EOF.
            raise EOFError from exc


def parse_editors(spec: str) -> list[tuple[str, str]]:
    if not spec:
        return list(DEFAULT_DISCOVERED)
    out: list[tuple[str, str]] = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            name, path = item.split(":", 1)
        else:
            name, path = item, item
        out.append((name.strip(), path.strip()))
    return out


def parse_pairs(spec: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in spec.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        key, value = item.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def resolve_custom(raw: str, args: argparse.Namespace) -> Optional[str]:
    tokens = raw.split()
    if not tokens:
        return None
    key = tokens[0]
    if args.which_map:
        return parse_pairs(args.which_map).get(key)
    return shutil.which(key)


def render_list(editors: list[tuple[str, str]], args, emit: Emitter) -> None:
    for i, (name, path) in enumerate(editors, 1):
        token = f"{i}." if args.list_format == "bare" else f"[{i}]"
        line = f"{token} {name}"
        if args.show_paths:
            line += f"  ({path})"
        emit(line)


def _invalid(args, emit: Emitter, message: str) -> None:
    if args.invalid_mode == "message":
        emit(message, fg="red")


def _finish(args, emit: Emitter, action: str, value: str, note: str = "") -> dict:
    emit("")
    emit(SAVED, fg="green")
    suffix = f"  (source={note})" if note else ""
    emit(f"[DEMO] action={action} value={value!r}{suffix}")
    return {"action": action, "value": value}


def _selection_flow(
    args, emit: Emitter, feed: InputFeeder, editors, prompt: str
) -> dict:
    primary = prompt.replace("{n}", str(len(editors)))
    emit("")
    while True:
        try:
            raw = feed.prompt(primary).strip()
        except EOFError:
            return _finish(
                args, emit, "disabled", "disabled", note="input closed (EOF)"
            )
        if raw == "":
            return _finish(args, emit, "disabled", "disabled")
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(editors):
                name, path = editors[idx - 1]
                return _finish(args, emit, "selected-number", path, note=name)
            _invalid(
                args,
                emit,
                f"'{raw}' is not a valid selection. Choose 1-{len(editors)}.",
            )
            continue
        resolved = resolve_custom(raw, args)
        if resolved:
            return _finish(args, emit, "custom", raw, note=resolved)
        _invalid(args, emit, f"'{raw}' was not found in PATH.")


def _custom_only_flow(args, emit: Emitter, feed: InputFeeder) -> dict:
    emit("")
    while True:
        try:
            raw = feed.prompt(NO_KNOWN).strip()
        except EOFError:
            return _finish(
                args, emit, "disabled", "disabled", note="input closed (EOF)"
            )
        if raw == "":
            return _finish(args, emit, "disabled", "disabled")
        resolved = resolve_custom(raw, args)
        if resolved:
            return _finish(args, emit, "custom", raw, note=resolved)
        _invalid(args, emit, f"'{raw}' was not found in PATH.")


def run(args, emit: Emitter, feed: InputFeeder) -> dict:
    if args.discovery_mode == "missing":
        emit(WARN_MISSING.format(editor=args.configured), fg="yellow")
    else:
        emit(MSG_UNCONFIGURED, fg="yellow")

    if args.header:
        emit("")
        emit(args.header, fg="cyan", bold=True)

    editors = [] if args.no_editors_found else parse_editors(args.editors)

    if not editors:
        return _custom_only_flow(args, emit, feed)

    emit("")
    render_list(editors, args, emit)
    return _selection_flow(args, emit, feed, editors, args.prompt)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="editors_demo.py",
        description="Interactive demo of the Slice 03-01 console editor-selection UI.",
    )
    p.add_argument(
        "--discovery-mode",
        choices=["missing", "unconfigured"],
        default="missing",
        help="Which warning precedes discovery (default: missing).",
    )
    p.add_argument(
        "--configured",
        default="code",
        help="Configured-but-missing editor name for the warning (default: code).",
    )
    p.add_argument(
        "--list-format",
        choices=["bare", "bracket"],
        default="bracket",
        help="Numbering style: '1. nvim' or '[1] nvim' (default: bracket).",
    )
    p.add_argument(
        "--show-paths",
        action="store_true",
        help="Append the resolved path: '[1] nvim  (/usr/bin/nvim)'.",
    )
    p.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=True,
        help="Enable typer colour (default).",
    )
    p.add_argument(
        "--no-color", dest="color", action="store_false", help="Disable colour."
    )
    p.add_argument(
        "--prompt",
        default=DEFAULT_PRIMARY_PROMPT,
        help="Primary selection prompt; '{n}' expands to the editor count.",
    )
    p.add_argument(
        "--invalid-mode",
        choices=["silent", "message"],
        default="message",
        help="Out-of-range/invalid handling (default: message).",
    )
    p.add_argument(
        "--header",
        default="Editor Setup",
        help="Header line above the list (always shown; default: 'Editor Setup').",
    )
    p.add_argument(
        "--editors",
        default="",
        help="Discovery set as 'name:path,name2:path2' (default: built-in sample).",
    )
    p.add_argument(
        "--no-editors-found",
        action="store_true",
        help="Simulate the empty-discovery branch.",
    )
    p.add_argument(
        "--which-map",
        default="",
        help="Override which() for custom validation: 'name:path,...'.",
    )
    p.add_argument(
        "--inputs",
        default=None,
        help="Scripted comma-separated inputs (skips the interactive prompt).",
    )
    p.add_argument(
        "--selftest", action="store_true", help="Run the assertion battery and exit."
    )
    return p


def drive(argv: list[str]) -> tuple[dict, list[str]]:
    args = build_parser().parse_args(argv)
    lines: list[str] = []
    emit = Emitter(color=False, capture=lines)
    script = args.inputs.split(",") if args.inputs is not None else None
    feed = InputFeeder(script, emit)
    result = run(args, emit, feed)
    return result, lines


def selftest() -> int:
    results: list[tuple[str, bool]] = []

    def check(name: str, cond: bool) -> None:
        results.append((name, bool(cond)))

    # A. numbered selection saves the resolved path
    res, lines = drive(["--inputs", "2", "--show-paths"])
    check("A numbered selection -> selected-number", res["action"] == "selected-number")
    check("A saves resolved path (vim)", res["value"] == "/usr/bin/vim")
    check("A list shows resolved paths", any("(/usr/bin/vim)" in ln for ln in lines))

    # B. out-of-range then valid (message mode)
    res, lines = drive(["--inputs", "99,1", "--invalid-mode", "message"])
    check(
        "B out-of-range re-prompts then succeeds",
        res["action"] == "selected-number" and res["value"] == "/usr/local/bin/nvim",
    )
    check("B invalid message shown", any("not a valid selection" in ln for ln in lines))

    # C. invalid silent -> no message
    _res, lines = drive(["--inputs", "99,1", "--invalid-mode", "silent"])
    check(
        "C silent mode shows no invalid message",
        not any("not a valid" in ln for ln in lines),
    )

    # D. empty -> disabled
    res, _lines = drive(["--inputs", ""])
    check(
        "D empty input -> disabled",
        res["action"] == "disabled" and res["value"] == "disabled",
    )

    # E. custom valid
    res, _lines = drive(
        ["--inputs", "myeditor", "--which-map", "myeditor:/opt/bin/myeditor"]
    )
    check(
        "E custom valid -> custom",
        res["action"] == "custom" and res["value"] == "myeditor",
    )

    # F. custom invalid then valid
    res, lines = drive(
        [
            "--inputs",
            "nope,myeditor",
            "--which-map",
            "myeditor:/opt/bin/myeditor",
            "--invalid-mode",
            "message",
        ]
    )
    check(
        "F custom invalid loops to valid",
        res["action"] == "custom" and res["value"] == "myeditor",
    )
    check("F custom invalid message", any("was not found in PATH" in ln for ln in lines))

    # G. no editors found -> custom-only prompt
    res, lines = drive(["--no-editors-found", "--inputs", ""])
    check(
        "G no-editors branch uses NO_KNOWN prompt",
        any(NO_KNOWN in ln for ln in lines),
    )
    check("G no-editors empty -> disabled", res["action"] == "disabled")

    # H. EOF -> disabled
    res, _lines = drive(["--inputs", "99", "--invalid-mode", "message"])
    check("H EOF -> disabled", res["action"] == "disabled")

    # I. discovery-mode warnings
    _res, lines = drive(["--discovery-mode", "missing", "--inputs", ""])
    check(
        "I missing-editor warning rendered",
        any("not found in PATH" in ln for ln in lines),
    )
    _res, lines = drive(["--discovery-mode", "unconfigured", "--inputs", ""])
    check(
        "I unconfigured message rendered",
        any("No editor configured" in ln for ln in lines),
    )

    # J. list formats
    _res, lines = drive(["--list-format", "bare", "--inputs", ""])
    check("J bare format '1. nvim'", any(ln.startswith("1. nvim") for ln in lines))
    _res, lines = drive(["--list-format", "bracket", "--inputs", ""])
    check("J bracket format '[1] nvim'", any(ln.startswith("[1] nvim") for ln in lines))

    # K. optional header
    _res, lines = drive(["--header", "Editor Setup", "--inputs", ""])
    check("K header rendered", "Editor Setup" in lines)

    print("=" * 72)
    print("SELFTEST: editor-selection UI demo")
    print("=" * 72)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failed = [n for n, ok in results if not ok]
    if failed:
        print(f"\nFAILED: {failed}")
        return 1
    print(f"\nAll {len(results)} checks passed.")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.selftest:
        return selftest()

    emit = Emitter(color=args.color)
    script = args.inputs.split(",") if args.inputs is not None else None
    feed = InputFeeder(script, emit)

    if script is None:
        typer.secho(
            "=== Editor-selection UI demo  "
            f"(list-format={args.list_format}, show-paths={args.show_paths}, "
            f"color={args.color}, invalid-mode={args.invalid_mode}) ===",
            fg=typer.colors.CYAN,
            err=True,
        )
        typer.echo("--- rendered preflight block (what the user sees) ---", err=True)

    run(args, emit, feed)
    return 0


if __name__ == "__main__":
    sys.exit(main())