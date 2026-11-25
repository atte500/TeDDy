"""Probe: which prose-wrapping strategy lets the terminal reflow a Message?

MRE 01 proved production hard-wraps at console width. MRE 02 falsified
``soft_wrap=True`` alone: paragraphs became width-invariant, but Rich still
lays list items out at ``console.width`` and at width 40 CROPS them
("... should lose ba"), so data is lost. The culprit is Markdown's internal
block layout, not only the outer wrap.

A reflowable body must render each prose block at an unbounded width (so
nothing folds or crops internally), then emit it so the terminal owns the fold.

This probe renders a realistic Message body through four prose strategies at
console widths 80 and 40 and reports width-invariance, cropping, marker
stripping, heading fidelity, and fenced byte fidelity.
"""

from __future__ import annotations

import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from teddy_executor.core.utils import message_renderer as prod
from teddy_executor.core.utils.markdown import split_fenced_segments
from teddy_executor.core.utils.message_renderer import inline_code_theme

BIG = 10_000

PARAGRAPH = (
    "This is a deliberately long paragraph that a communicating turn would "
    "print as its Message body. It keeps going so that it clearly exceeds a "
    "narrow terminal width, forcing the renderer to choose between wrapping "
    "the text itself and leaving one logical line for the terminal to fold "
    "and reflow when the user resizes the window."
)

BULLET2_TEXT = "Inline teddy resume -p should lose backticks."

LONG_COMMAND = (
    "uv run teddy context -c README.md -c pyproject.toml "
    "-c docs/project/PROJECT.md --only"
)

BODY = f"""## Heads up

{PARAGRAPH}

- **Bold** should lose its asterisks.
- Inline `teddy resume -p` should lose backticks.

```bash
echo before
{LONG_COMMAND}
echo after
```
"""

STRATEGIES = ("current", "soft_wrap_only", "wide_print", "render_lines_text")


def _render_lines_text(content: str, console: Console) -> None:
    """Render at an unbounded width, then emit each logical line soft-wrapped."""
    try:
        options = console.options.update(max_width=BIG)
    except TypeError:
        options = console.options.update(width=BIG)
    for line in console.render_lines(Markdown(content), options=options, pad=False):
        text = Text()
        for segment in line:
            if segment.control:
                continue
            text.append(segment.text, style=segment.style)
        console.print(text.rstrip(), soft_wrap=True)


def _prose(strategy: str, content: str, console: Console) -> None:
    if strategy == "current":
        console.print(Markdown(content))
    elif strategy == "soft_wrap_only":
        console.print(Markdown(content), soft_wrap=True)
    elif strategy == "wide_print":
        console.print(Markdown(content), width=BIG, soft_wrap=True)
    elif strategy == "render_lines_text":
        _render_lines_text(content, console)
    else:
        raise ValueError(strategy)


def render(strategy: str, width: int) -> str:
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=width,
        force_terminal=False,
        color_system=None,
        theme=inline_code_theme(),
    )
    for segment in split_fenced_segments(BODY):
        if segment.kind == "prose":
            _prose(strategy, segment.content, console)
        else:
            prod._emit_fenced_block(segment, console)
    return buffer.getvalue()


def evaluate(strategy: str):
    try:
        out80 = render(strategy, 80)
        out40 = render(strategy, 40)
    except Exception as exc:  # noqa: BLE001 - probe reports failures verbatim
        return {"error": repr(exc)}, "", ""
    lines80 = out80.splitlines()
    checks = {
        "width-invariant": out80 == out40,
        "paragraph intact @40": PARAGRAPH in out40,
        "bullet not cropped @40": BULLET2_TEXT in out40,
        "no bold markers": "**Bold**" not in out80,
        "no inline backticks": "`teddy resume -p`" not in out80,
        "heading text, no hashes": "## Heads up" not in out80
        and any(line.strip() == "Heads up" for line in lines80),
        "fenced command byte-exact": any(
            line.rstrip() == LONG_COMMAND for line in lines80
        ),
        "no giant padding": max((len(line) for line in lines80), default=0) < 2000,
    }
    return checks, out80, out40


def main() -> None:
    results = {}
    for strategy in STRATEGIES:
        checks, out80, out40 = evaluate(strategy)
        results[strategy] = checks
        print(f"=== {strategy} ===")
        if "error" in checks:
            print(f"  ERROR: {checks['error']}\n")
            continue
        for label, ok in checks.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        longest80 = max((len(line) for line in out80.splitlines()), default=0)
        longest40 = max((len(line) for line in out40.splitlines()), default=0)
        print(f"  longest emitted line @80: {longest80}")
        print(f"  longest emitted line @40: {longest40}")
        print()

    print("=== VERDICT ===")
    winners = [s for s, c in results.items() if "error" not in c and all(c.values())]
    for strategy in STRATEGIES:
        checks = results[strategy]
        if "error" in checks:
            verdict = "ERROR"
        elif all(checks.values()):
            verdict = "WINNER"
        else:
            verdict = "rejected"
        print(f"  {strategy:20s} {verdict}")
    print()
    if winners:
        print(f"=> Winner(s): {', '.join(winners)}. Build the replica proof on one.")
        sys.exit(0)
    print("=> No strategy passed every check; inspect failures above and iterate.")
    sys.exit(1)


if __name__ == "__main__":
    main()
