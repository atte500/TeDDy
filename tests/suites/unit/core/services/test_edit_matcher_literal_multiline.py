"""Regression tests: EditMatcher literal text-editor find & replace semantics.

A multi-line FIND block must match only when it appears VERBATIM as a
contiguous substring of the file content (newlines inside the FIND must
correspond to real file line breaks; starting or ending mid-line is fine
otherwise). A single-line FIND keeps its intra-line fragment matching,
enabling surgical replacement that preserves both head and tail of a line.
"""

from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.validation_rules.edit_matcher import (
    find_best_match,
)

_BASE = (
    "1. **Hypothesis:** the repeated EDIT validation failures could be a bug "
    "in the EDIT pipeline, since the session runs inside the tool itself. "
    "**Observation:** full source read of validation and simulation modules, "
    "plus a repo-wide census of similarity computation and reporting sites. "
    "**Conclusion:** not a correctness bug - one matcher serves both "
    "validation and execution; the reported score is the correct score. "
)
_LONG_ENTRY = (_BASE + _BASE + _BASE)[:1500] + " end-of-entry-marker"
_LINE_2 = (
    "2. **Hypothesis:** the substring boost gate is the sole rescue path "
    "for partial-line anchoring."
)
_FILE_CONTENT = (
    "## Investigation History\n"
    + _LONG_ENTRY
    + "\n"
    + _LINE_2
    + "\n"
    + "## Solution\n"
    + "TBD.\n"
)


class TestLiteralMultilineFindReplace:
    """Locks text-editor find & replace semantics for multi-line FIND blocks."""

    def test_multiline_find_verbatim_substring_matches(self):
        # FIND starts mid-line, runs through end-of-line, plus the next line.
        find_block = _LONG_ENTRY[600:] + "\n" + _LINE_2 + "\n"
        assert find_block in _FILE_CONTENT

        match, score, is_ambiguous, _ = find_best_match(_FILE_CONTENT, find_block)

        assert score >= DEFAULT_SIMILARITY_THRESHOLD
        assert match == find_block, "match must equal the literal FIND block"
        assert is_ambiguous is False

    def test_multiline_find_replacement_preserves_line_head(self):
        # End-to-end: the replacement must keep the text preceding the FIND
        # block on the first (long single) line and touch nothing else.
        find_block = _LONG_ENTRY[600:] + "\n" + _LINE_2 + "\n"
        replacement = "REPLACED-ENTRY-TAIL\nREPLACED-NEXT-LINE\n"

        result, scores = EditSimulator().simulate_edits(
            _FILE_CONTENT, [{"find": find_block, "replace": replacement}]
        )

        assert scores == [1.0]
        assert _LONG_ENTRY[:600] in result, "line head must be preserved"
        assert "REPLACED-ENTRY-TAIL" in result
        assert "REPLACED-NEXT-LINE" in result
        assert "## Solution" in result, "trailing content must be untouched"

    def test_midline_fragment_with_newline_is_rejected(self):
        # The FIND claims a line break after a mid-line fragment, but the
        # file line continues after it -> not a literal substring.
        find_block = _LONG_ENTRY[600:690] + "\n" + _LINE_2 + "\n"
        assert find_block not in _FILE_CONTENT

        _, score, _, _ = find_best_match(_FILE_CONTENT, find_block)

        assert score < DEFAULT_SIMILARITY_THRESHOLD

    def test_single_line_fragment_still_matches_intra_line(self):
        # Control: single-line fragment keeps its surgical intra-line match.
        fragment = _LONG_ENTRY[600:690]

        match, score, _, _ = find_best_match(_FILE_CONTENT, fragment + "\n")

        assert score >= DEFAULT_SIMILARITY_THRESHOLD
        assert match == fragment

    def test_multiline_find_ending_midline_without_terminator_matches(self):
        # A multi-line FIND ending mid-line (no trailing newline) is still a
        # verbatim contiguous substring and MUST match.
        find_block = "## Investigation History\n" + _LONG_ENTRY[:50]
        assert find_block in _FILE_CONTENT

        match, score, _, _ = find_best_match(_FILE_CONTENT, find_block)

        assert score >= DEFAULT_SIMILARITY_THRESHOLD
        assert match == find_block

    def test_claimed_linebreak_where_line_continues_is_rejected(self):
        # Same shape as above but WITH a trailing newline on the final
        # mid-line fragment: the claimed line break does not exist in the
        # file, so the block is not a substring and MUST NOT match.
        find_block = "## Investigation History\n" + _LONG_ENTRY[:50] + "\n"
        assert find_block not in _FILE_CONTENT

        _, score, _, _ = find_best_match(_FILE_CONTENT, find_block)

        assert score < DEFAULT_SIMILARITY_THRESHOLD
