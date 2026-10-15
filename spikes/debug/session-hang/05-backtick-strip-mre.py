"""MRE: prove trailing-open-fence detection bounds the payload.

The real turn-24 plan.md contained a single ~252,310-backtick run that was
NEVER CLOSED (an unclosed opening code fence). The user has since removed it, so
this MRE deterministically reconstructs an equivalent degenerate plan and
compares the REAL unbounded ContextService._format_session_history against the
sanitized sandbox replica (which strips the dangling fence).

    uv run python spikes/debug/session-hang/05-backtick-strip-mre.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from replica_embed_sanitizer import (  # noqa: E402
    format_session_history_sanitized,
    strip_trailing_open_fence,
)

from teddy_executor.core.services.context_service import ContextService  # noqa: E402

DEGENERATE_RUN = 252_310  # matches the measured turn-24 all-backtick line

# A GENUINE nested fence: a 4-backtick fence wrapping a 3-backtick fence. This is
# legitimate Markdown and MUST survive sanitization byte-for-byte.
LEGIT_NESTED_FENCE = (
    "````markdown\n"
    "An example fence:\n"
    "```python\n"
    "print('hello')\n"
    "```\n"
    "````\n"
)


def main() -> None:
    real_body = (
        "# Plan\n\n## Rationale\nReal plan content above the degeneration.\n\n"
        + "`" * DEGENERATE_RUN
        + "\n"
    )
    path = ".teddy/sessions/example/24/plan.md"
    paths = [path]
    contents = {path: real_body}

    real_parts = ContextService._format_session_history(None, paths, contents)  # type: ignore[arg-type]
    real_total = sum(len(p) for p in real_parts)

    sanitized_parts = format_session_history_sanitized(paths, contents)
    sanitized_total = sum(len(p) for p in sanitized_parts)

    print(f"degenerate_run={DEGENERATE_RUN}")
    print(f"REAL      (unbounded) section_total={real_total}")
    print(f"SANITIZED (replica)   section_total={sanitized_total}")
    print(f"reduction_factor={real_total / sanitized_total:.0f}x")

    assert real_total > 700_000, "expected the unbounded path to blow up"
    assert sanitized_total < 2_000, "expected sanitization to collapse the payload"
    print("PASS: backtick sanitization bounds the payload without a size cap")

    # A GENUINE 4-backtick nested fence must be preserved unchanged, proving the
    # detector only targets UNCLOSED fences.
    preserved = strip_trailing_open_fence(LEGIT_NESTED_FENCE)
    assert preserved == LEGIT_NESTED_FENCE, (
        "sanitizer must NOT alter a legitimate nested fence:\n"
        f"expected={LEGIT_NESTED_FENCE!r}\n"
        f"got={preserved!r}"
    )
    print("PASS: legitimate 4-backtick nested fence preserved byte-for-byte")

    # A normal balanced code block must also survive unchanged.
    balanced = "# Plan\n\n```python\nprint('hi')\n```\n"
    assert strip_trailing_open_fence(balanced) == balanced
    print("PASS: balanced code block preserved byte-for-byte")


if __name__ == "__main__":
    main()