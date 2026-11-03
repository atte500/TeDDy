"""Unit: plan-view rendering truncates at the plan display cap with a hint-less notice.

``render_plan_view`` is a pure function. The notice is a plain
``[Showing first N of M lines.]`` line and never carries the READ-tool
"Use the 'Lines' parameter" hint.
"""

from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    render_plan_view,
)


def _numbered_plan(line_count: int) -> str:
    return "\n".join(f"line {i}" for i in range(1, line_count + 1))


def test_render_truncates_a_long_plan_with_hint_less_notice():
    rendered = render_plan_view(_numbered_plan(6000), 5000)

    lines = rendered.splitlines()
    assert lines[:5000] == [f"line {i}" for i in range(1, 5001)]
    assert lines[5000] == "[Showing first 5000 of 6000 lines.]"
    assert "Use the 'Lines' parameter" not in rendered


def test_render_at_the_cap_is_unchanged():
    content = _numbered_plan(5000)

    assert render_plan_view(content, 5000) == content


def test_render_below_the_cap_is_unchanged():
    content = _numbered_plan(10)

    assert render_plan_view(content, 5000) == content


def test_render_empty_content_is_unchanged():
    assert render_plan_view("", 5000) == ""


def test_render_with_zero_cap_is_unchanged():
    content = _numbered_plan(10)

    assert render_plan_view(content, 0) == content
