"""Contract: the README documents the guardrail CLI flags.

The README is the user-facing reference for the CLI surface. The
``--max-turns`` and ``--max-cost`` flags bound a non-interactive run, so
operators must discover them from the README Optional Flags list instead of
the source code.

The assertion is scoped to the ``### Optional Flags`` section on purpose:
the Environment Variables table already names ``TEDDY_MAX_TURNS`` and
``TEDDY_MAX_SESSION_COST``, so a whole-file check would pass even when the
flags are missing from the flag list.
"""

from pathlib import Path

import pytest

README = Path(__file__).resolve().parents[3] / "README.md"


def _optional_flags_section() -> str:
    """Returns the README ``### Optional Flags`` section body."""
    text = README.read_text(encoding="utf-8")
    marker = "### Optional Flags"
    start = text.index(marker) + len(marker)
    remainder = text[start:]
    end = remainder.find("\n### ")
    return remainder if end == -1 else remainder[:end]


@pytest.mark.parametrize("flag", ["--max-turns", "--max-cost"])
def test_optional_flags_list_documents_the_guardrail_flag(flag):
    """The Optional Flags list names each guardrail flag in backticks."""
    section = _optional_flags_section()

    assert f"`{flag}`" in section, (
        f"README Optional Flags list must document `{flag}`, got section:\n{section}"
    )
