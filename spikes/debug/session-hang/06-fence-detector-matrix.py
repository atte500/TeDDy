"""Probe: does strip_trailing_open_fence reliably preserve genuine code blocks?

Answers the reliability question with a matrix of cases:
  - PRESERVE: well-formed Markdown (balanced fences, backtick AND tilde,
    nested fences, mixed blocks, inline code, indented code) MUST be returned
    byte-for-byte unchanged.
  - COLLAPSE: an opened-but-never-closed fence (the observed defect, in both
    backtick and tilde form) MUST be removed.
  - AMBIGUOUS: mismatched fence lengths are already malformed; we DOCUMENT the
    (CommonMark-consistent) behavior rather than assert it.

    uv run python spikes/debug/session-hang/06-fence-detector-matrix.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from replica_embed_sanitizer import strip_trailing_open_fence  # noqa: E402

# (name, content) -- MUST be returned byte-for-byte unchanged.
PRESERVE: list[tuple[str, str]] = [
    ("balanced-backtick", "# T\n\n```python\nprint('hi')\n```\n"),
    ("balanced-tilde", "# T\n\n~~~python\nprint('hi')\n~~~\n"),
    (
        "nested-4-wraps-3",
        "````markdown\nAn example fence:\n```python\nprint('hello')\n```\n````\n",
    ),
    ("multiple-mixed-blocks", "```\na\n```\ntext\n~~~\nb\n~~~\n"),
    ("inline-code-mid-line", "Use `foo` and ``bar`` here.\n"),
    ("inline-code-own-line", "``foo``\n"),
    ("indented-code", "    ```\n    code\n    ```\n"),
    ("no-fences", "Just prose.\n\nNo fences at all.\n"),
    ("prose-after-block", "text\n\n```py\nx = 1\n```\n\nmore prose\n"),
    ("block-at-eof-no-newline", "```python\nx = 1\n```"),
]

# (name, content, expected_result) -- an UNCLOSED fence MUST be removed.
COLLAPSE: list[tuple[str, str, str]] = [
    ("giant-backtick-run", "# Plan\n\n" + "`" * 10_000 + "\n", "# Plan\n\n"),
    ("giant-tilde-run", "# Plan\n\n" + "~" * 10_000 + "\n", "# Plan\n\n"),
    ("unclosed-opener-with-content", "```python\nprint('hi')\n", "print('hi')\n"),
    ("unclosed-tilde-with-content", "~~~python\nprint('hi')\n", "print('hi')\n"),
]

# (name, content) -- already-malformed; DOCUMENT (not assert) the behavior.
AMBIGUOUS: list[tuple[str, str]] = [
    ("mismatched-close-longer", "```python\nprint('a')\n````\nprint('b')\n```\n"),
    ("odd-fence-count", "```\nA\n```\nB\n```\n"),
    ("block-containing-giant-run", "```\n" + "`" * 100 + "\n```\n"),
]


def main() -> None:
    failures = 0

    print("=== PRESERVE (well-formed Markdown; must be unchanged) ===")
    for name, content in PRESERVE:
        result = strip_trailing_open_fence(content)
        ok = result == content
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    print("\n=== COLLAPSE (unclosed fence; must be removed) ===")
    for name, content, expected in COLLAPSE:
        result = strip_trailing_open_fence(content)
        ok = result == expected
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} -> {result[:32]!r}")

    print("\n=== AMBIGUOUS (already malformed; documented, CommonMark-consistent) ===")
    for name, content in AMBIGUOUS:
        result = strip_trailing_open_fence(content)
        changed = result != content
        print(f"  [{'MUTATED' if changed else 'PRESERVED'}] {name}")

    print(f"\n{'ALL PRESERVE+COLLAPSE PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    assert failures == 0


if __name__ == "__main__":
    main()