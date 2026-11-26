"""Invariant tests for the canonical reviewer context-panel shapes.

Each shape exists to make one panel branch reachable, so the shapes are
asserted against the same history predicate the panel builder consults rather
than against hand-written expectations.
"""

from teddy_executor.core.utils.markdown import is_session_history_path

from tests.harness.setup.reviewer_context_scenarios import (
    SESSION_ROOT,
    reviewer_project_context,
)


def test_populated_shape_owns_every_scope_and_a_history_entry():
    context = reviewer_project_context("populated")

    assert context is not None
    assert context.session_root == SESSION_ROOT
    assert {item.scope for item in context.items} == {"Session", "Turn"}
    assert any(
        is_session_history_path(item.path, SESSION_ROOT) for item in context.items
    )


def test_history_less_shape_renders_no_history_group():
    context = reviewer_project_context("history_less")

    assert context is not None
    assert context.items
    assert not any(
        is_session_history_path(item.path, SESSION_ROOT) for item in context.items
    )


def test_no_context_shape_returns_nothing_to_render():
    assert reviewer_project_context("none") is None
