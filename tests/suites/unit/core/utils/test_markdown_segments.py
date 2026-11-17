"""Contract tests for the `split_fenced_segments` body splitter."""

from dataclasses import FrozenInstanceError

import pytest

from teddy_executor.core.utils.markdown import MessageSegment, split_fenced_segments


def test_split_fenced_segments_returns_prose_only_body_as_one_segment():
    """A body with no fence yields one prose segment carrying all of its bytes."""
    body = "Just prose.\n\nSecond paragraph.\n"

    segments = split_fenced_segments(body)

    assert len(segments) == 1
    prose = segments[0]
    assert prose.kind == "prose"
    assert prose.content == body
    assert (prose.info, prose.opening, prose.closing) == ("", "", "")


def test_split_fenced_segments_returns_no_segments_for_an_empty_body():
    assert split_fenced_segments("") == []


_DELIMITER_CASES = [
    (
        "tagged-backtick",
        "```bash\necho hi\n```",
        ("bash", "```bash", "```", "echo hi"),
    ),
    ("untagged-backtick", "```\nplain\n```", ("", "```", "```", "plain")),
    (
        "indented-fence",
        "  ```python\nx = 1\n  ```",
        ("python", "  ```python", "  ```", "x = 1"),
    ),
    (
        "tilde-fence",
        "~~~yaml\nkey: value\n~~~",
        ("yaml", "~~~yaml", "~~~", "key: value"),
    ),
    ("longer-closing-run", "```\ncode\n`````", ("", "```", "`````", "code")),
    (
        "unknown-info-string",
        "```teddy-plan\n# Plan\n```",
        ("teddy-plan", "```teddy-plan", "```", "# Plan"),
    ),
    (
        "info-string-trailing-spaces",
        "```bash  \necho hi\n```",
        ("bash", "```bash  ", "```", "echo hi"),
    ),
    (
        "crlf-opener",
        "```bash\r\necho hi\r\n```",
        ("bash", "```bash\r", "```", "echo hi\r"),
    ),
]


@pytest.mark.parametrize(
    ("body", "expected"),
    [(body, expected) for _, body, expected in _DELIMITER_CASES],
    ids=[name for name, _, _ in _DELIMITER_CASES],
)
def test_split_fenced_segments_reads_delimiters_verbatim(body, expected):
    """`opening` and `closing` carry the raw delimiter lines; `info` is stripped."""
    (segment,) = split_fenced_segments(body)

    assert segment.kind == "fence"
    assert (segment.info, segment.opening, segment.closing, segment.content) == expected


def test_split_fenced_segments_separates_surrounding_prose():
    segments = split_fenced_segments("Before.\n\n```bash\necho hi\n```\n\nAfter.\n")

    assert [segment.kind for segment in segments] == ["prose", "fence", "prose"]
    assert segments[0].content == "Before.\n"
    assert segments[1].opening == "```bash"
    assert segments[2].content == "\nAfter.\n"


def test_split_fenced_segments_keeps_tilde_block_holding_backtick_run():
    """A backtick run inside a tilde block is content, not a closing fence."""
    (segment,) = split_fenced_segments("~~~\n```python\nprint(1)\n```\n~~~\n")

    assert segment.opening == "~~~"
    assert segment.closing == "~~~"
    assert segment.content == "```python\nprint(1)\n```"


def test_split_fenced_segments_nested_four_backticks_wrap_three():
    """A longer opening fence is closed only by a run at least as long."""
    body = "````markdown\n```python\nprint(1)\n```\n````\n"

    (segment,) = split_fenced_segments(body)

    assert segment.opening == "````markdown"
    assert segment.closing == "````"
    assert segment.content == "```python\nprint(1)\n```"


def test_split_fenced_segments_unclosed_fence_has_empty_closing():
    (segment,) = split_fenced_segments("```python\nprint(1)\n")

    assert segment.opening == "```python"
    assert segment.closing == ""
    assert segment.content == "print(1)\n"


def test_split_fenced_segments_different_delimiter_character_does_not_close():
    (segment,) = split_fenced_segments("```\ncode\n~~~\n")

    assert segment.closing == ""
    assert segment.content == "code\n~~~\n"


def test_split_fenced_segments_empty_fence_keeps_both_delimiters():
    (segment,) = split_fenced_segments("```\n```\n")

    assert segment.kind == "fence"
    assert segment.content == ""
    assert segment.opening == segment.closing == "```"


def test_split_fenced_segments_drops_whitespace_only_prose():
    """The renderer owns spacing around fences, so a blank run carries nothing."""
    segments = split_fenced_segments("```\na\n```\n\n```\nb\n```\n")

    assert [segment.kind for segment in segments] == ["fence", "fence"]
    assert split_fenced_segments("\n\n") == []


def test_message_segment_is_frozen():
    segment = MessageSegment(kind="prose", content="text")

    with pytest.raises(FrozenInstanceError):
        setattr(segment, "content", "other")
