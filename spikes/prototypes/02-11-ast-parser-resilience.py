#!/usr/bin/env python3
"""
Standalone Feature Prototype: Slice 02-11 (AST Parser Resilience)

De-risks two parser improvements:
1. Stripping trailing text on closing fence lines (6+ backticks or tildes)
2. Silently ignoring trailing code blocks after the last action

Usage:
    poetry run python spikes/prototypes/02-11-ast-parser-resilience.py         # Non-interactive verification
    poetry run python spikes/prototypes/02-11-ast-parser-resilience.py --verify  # Explicit verification
    poetry run python spikes/prototypes/02-11-ast-parser-resilience.py --interactive  # Interactive testing
    poetry run python spikes/prototypes/02-11-ast-parser-resilience.py --boot-check  # 5-sec smoke test
"""

import re
import sys
import subprocess


def strip_trailing_fence_text(text: str) -> str:
    """
    Strip trailing text on fence lines with 6+ consecutive backticks or tildes.

    For each line, if the line (after optional leading whitespace) consists of
    6 or more consecutive backticks or tildes followed by additional non-whitespace
    content, strip that trailing content entirely.

    This handles both:
    - `~~~~~~ trailing text` (space between fence and trailing text)
    - `~~~~~~trailingtext` (immediately adjacent trailing text)
    - `    ~~~~~~ trailing text` (indented fences)

    Fences with fewer than 6 characters (e.g., `~~~~`, ``````) are NOT modified.
    Empty lines or lines without fence characters are NOT modified.
    Fences with ONLY the fence characters (no trailing text) are NOT modified.
    """
    lines = text.split("\n")
    result = []
    # Pattern: optional leading whitespace, 6+ backticks OR 6+ tildes (pure sequences only), then optional trailing content
    pattern = re.compile(r"^(\s*)(\~{6,}|\`{6,})(.*)$")

    for line in lines:
        match = pattern.match(line)
        if match:
            trailing = match.group(3)
            # Only strip trailing content if it does NOT contain any backtick or tilde.
            # This prevents corrupting lines like "~~~~~~` trailing" where fence
            # characters are mixed within content.
            if trailing is not None and trailing.strip():
                if not any(c in trailing for c in ("`", "~")):
                    # Reconstruct line with only whitespace + fence characters
                    line = match.group(1) + match.group(2)
            # If trailing is empty/whitespace or contains fence chars, keep original.
        result.append(line)

    return "\n".join(result)


def test_strip_trailing_fence_text():
    """Run all assertion-based tests for strip_trailing_fence_text."""
    results = {"pass": 0, "fail": 0, "total": 0}

    def check(name: str, actual: str, expected: str):
        results["total"] += 1
        if actual == expected:
            results["pass"] += 1
            print(f"  ✓ {name}")
        else:
            results["fail"] += 1
            print(f"  ✗ {name}")
            print(f"      Expected: {expected!r}")
            print(f"      Actual:   {actual!r}")

    # --- Test 1: 6-tilde closing fence with trailing text ---
    check(
        "6-tilde fence with trailing text",
        strip_trailing_fence_text("~~~~~~ trailing text"),
        "~~~~~~",
    )

    # --- Test 2: 6-backtick closing fence with trailing text ---
    check(
        "6-backtick fence with trailing text",
        strip_trailing_fence_text("`````` trailing text"),
        "``````",
    )

    # --- Test 3: 4-tilde fence (too short) should NOT be stripped ---
    check(
        "4-tilde fence with trailing text (below threshold)",
        strip_trailing_fence_text("~~~~ trailing text"),
        "~~~~ trailing text",
    )

    # --- Test 4: 6-tilde fence with immediately adjacent trailing text ---
    check(
        "6-tilde fence with adjacent trailing text (no space)",
        strip_trailing_fence_text("~~~~~~python"),
        "~~~~~~",
    )

    # --- Test 5: Indented 6-tilde fence with trailing text ---
    check(
        "Indented 6-tilde fence with trailing text",
        strip_trailing_fence_text("    ~~~~~~ trailing text"),
        "    ~~~~~~",
    )

    # --- Test 6: Fence with ONLY characters (no trailing text) ---
    check(
        "Fence with only characters (no trailing text)",
        strip_trailing_fence_text("~~~~~~"),
        "~~~~~~",
    )

    # --- Test 7: Fence with only characters and trailing whitespace ---
    check(
        "Fence with only characters and trailing whitespace",
        strip_trailing_fence_text("~~~~~~   "),
        "~~~~~~   ",
    )

    # --- Test 8: 8-tilde fence with trailing text ---
    check(
        "8-tilde fence with trailing text",
        strip_trailing_fence_text("~~~~~~~~ trailing text"),
        "~~~~~~~~",
    )

    # --- Test 9: Empty string ---
    check(
        "Empty string",
        strip_trailing_fence_text(""),
        "",
    )

    # --- Test 10: No fence lines at all ---
    check(
        "No fence lines",
        strip_trailing_fence_text("Hello world\nThis is normal text"),
        "Hello world\nThis is normal text",
    )

    # --- Test 11: Multiple fence lines in one text ---
    check(
        "Multiple fence lines",
        strip_trailing_fence_text("~~~~~~ first\n`````` second\n~~~~~~ third"),
        "~~~~~~\n``````\n~~~~~~",
    )

    # --- Test 12: Mixed content with regular lines between fences ---
    check(
        "Mixed content with regular lines",
        strip_trailing_fence_text(
            "Normal line\n~~~~~~ artifact\nAnother normal\n`````` more text"
        ),
        "Normal line\n~~~~~~\nAnother normal\n``````",
    )

    # --- Test 13: Line starting with backticks but fewer than 6 ---
    check(
        "3-backtick fence with trailing text (below threshold)",
        strip_trailing_fence_text("``` trailing text"),
        "``` trailing text",
    )

    # --- Test 14: Tilde and backtick mix (not purely one character type) ---
    check(
        "Mixed tilde/backtick (should not match pure fence pattern)",
        strip_trailing_fence_text("~~~~~~` trailing"),
        "~~~~~~` trailing",
    )

    # --- Test 15: Edge case - text line that starts with fence chars mid-content ---
    check(
        "Fence chars mid-content (not start of line)",
        strip_trailing_fence_text("Some text ~~~~~~ trailing"),
        "Some text ~~~~~~ trailing",
    )

    print(f"\n  Results: {results['pass']}/{results['total']} passed", end="")
    if results["fail"] > 0:
        print(f", {results['fail']} FAILED")
    else:
        print()
    return results["fail"] == 0


def test_mistletoe_parsing():
    """Verify that mistletoe can parse plans with trailing fence text after preprocessing."""
    from mistletoe.block_token import Document
    from mistletoe.block_token import Heading, CodeFence, BlockCode

    print("\n  --- Mistletoe Integration Tests ---")

    # Test A: Plan with trailing fence text → should parse as valid AST
    plan = """# Test Plan
- **Status:** Test

## Rationale
````text
Some rationale.
````

## Action Plan

### `READ`
- **Resource:** [test.txt](/test.txt)
- **Description:** Read a test file.
~~~~~~ trailing text artifact"""
    cleaned = strip_trailing_fence_text(plan)
    doc = Document(cleaned)

    # Should have at least a heading and not crash
    headings = [
        n for n in doc.children if isinstance(n, Heading) and n.level == 1
    ]
    assert len(headings) == 1, f"Expected 1 H1 heading, got {len(headings)}"
    print("  ✓ Plan with trailing fence text → valid AST (H1 present)")

    # Test B: Plan with trailing code block after last action
    plan2 = """# Another Test
- **Status:** Test

## Rationale
````text
Rationale.
````

## Action Plan

### `READ`
- **Resource:** [readme.md](/readme.md)
- **Description:** Read the readme.

````text
This is an unexplained trailing code block.
````"""
    cleaned2 = strip_trailing_fence_text(plan2)
    doc2 = Document(cleaned2)

    # Should have H1 and H2 headings
    h1_count = len(
        [n for n in doc2.children if isinstance(n, Heading) and n.level == 1]
    )
    h2_count = len(
        [n for n in doc2.children if isinstance(n, Heading) and n.level == 2]
    )
    assert h1_count >= 1, f"Expected at least 1 H1, got {h1_count}"
    assert h2_count >= 2, f"Expected at least 2 H2 (Rationale + Action Plan), got {h2_count}"

    # The trailing code block should be a CodeFence or BlockCode node
    trailing_nodes = [
        n
        for n in doc2.children
        if isinstance(n, (CodeFence, BlockCode))
    ]
    # It's OK if mistletoe parses it; the production parser should skip it
    print(f"  ✓ Plan with trailing code block → valid AST ({len(trailing_nodes)} code block(s) found, parser will skip)")

    # Test C: Clean plan (no artifacts) should be unchanged by preprocessor
    plan3 = """# Clean Plan
- **Status:** Test

## Rationale
````text
Rationale.
````

## Action Plan

### `READ`
- **Resource:** [clean.txt](/clean.txt)
- **Description:** Read a clean file."""
    cleaned3 = strip_trailing_fence_text(plan3)
    assert cleaned3 == plan3, "Clean plan should be unchanged"
    print("  ✓ Clean plan unchanged after preprocessing")

    print("  ✓ All mistletoe integration tests passed")


def run_verification():
    """Run full verification suite."""
    print("=== AST Parser Resilience Prototype ===")
    print("Verification mode: Running assertions...\n")

    success = test_strip_trailing_fence_text()
    test_mistletoe_parsing()

    print("\n---")
    if success:
        print("✓ All assertions passed!")
        sys.exit(0)
    else:
        print("✗ Some assertions FAILED!")
        sys.exit(1)


def run_interactive():
    """Simplified interactive mode: paste/type a line, instantly see result."""
    print("=== AST Parser Resilience Prototype ===")
    print("Interactive mode: Type or paste a line → see cleaned result.")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            raw = input("> ")
            if raw.strip().lower() in ("exit", "quit"):
                print("Exiting...")
                break

            result = strip_trailing_fence_text(raw)
            # Only print if different, else show "unchanged"
            if result != raw:
                print(f"  → {result}")
            else:
                print("  (unchanged)")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break


def run_file_or_pipe():
    """Process stdin or a file path argument.

    Usage:
        echo '~~~~~~ trailing text' | python 02-11-ast-parser-resilience.py
        python 02-11-ast-parser-resilience.py path/to/plan.md
    """
    import os

    # Check for a file argument (non-flag arg)
    non_flag_args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if non_flag_args:
        filepath = non_flag_args[0]
        if not os.path.isfile(filepath):
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        result = strip_trailing_fence_text(content)
        print(result)
        return

    # Otherwise read from stdin (pipe)
    if not sys.stdin.isatty():
        content = sys.stdin.read()
        result = strip_trailing_fence_text(content)
        print(result)
        return

    # No input source — show help
    print("Usage:")
    print("  python 02-11-ast-parser-resilience.py [path/to/file]      # Process a file")
    print("  echo '<text>' | python 02-11-ast-parser-resilience.py     # Pipe text")
    print("  python 02-11-ast-parser-resilience.py --interactive       # REPL mode")
    print("  python 02-11-ast-parser-resilience.py --verify            # Run assertions")


def run_boot_check():
    """Run a 5-second smoke test by invoking --verify as a subprocess."""
    proc = subprocess.run(
        [sys.executable, __file__, "--verify"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if proc.returncode == 0:
        print("✓ Boot check passed (5-second subprocess)")
    else:
        print("✗ Boot check FAILED")
        print(proc.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if "--interactive" in sys.argv:
        run_interactive()
    elif "--boot-check" in sys.argv:
        run_boot_check()
    elif "--verify" in sys.argv:
        run_verification()
    else:
        # Check if we have a file argument or piped input (non-tty stdin)
        non_flag_args = [a for a in sys.argv[1:] if not a.startswith("--")]
        if non_flag_args or not sys.stdin.isatty():
            run_file_or_pipe()
        elif len(sys.argv) == 1:
            # No arguments at all — default to verification
            run_verification()
        else:
            print(f"Unknown arguments: {sys.argv[1:]}")
            print("Usage: python 02-11-ast-parser-resilience.py [--verify | --interactive | --boot-check | path/to/file]")
            sys.exit(1)