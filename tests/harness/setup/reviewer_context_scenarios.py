"""Canonical context-panel shapes for reviewer tests.

The reviewer's context pane is built from a `ProjectContext` DTO, so a
navigation scenario needs a panel that carries every group (System, Session,
Turn, History), one that carries no history, and none at all. Each shape is
expressed through paths the real predicates classify, not through hand-written
labels, so a shape keeps meaning what its name says.
"""

from __future__ import annotations

from typing import Literal, Optional

from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)

ReviewerContextShape = Literal["populated", "history_less", "none"]

SESSION_ROOT = ".teddy/sessions/20260101_120000-navigation"
SESSION_ITEM_PATH = "src/teddy_executor/container.py"
TURN_ITEM_PATH = "docs/project/slices/04-07-section-navigation.md"
HISTORY_PLAN_PATH = f"{SESSION_ROOT}/01/plan.md"
HISTORY_REPORT_PATH = f"{SESSION_ROOT}/01/report.md"


def _item(path: str, scope: str, token_count: int) -> ContextItem:
    return ContextItem(path=path, token_count=token_count, git_status="M", scope=scope)


def reviewer_project_context(
    shape: ReviewerContextShape,
) -> Optional[ProjectContext]:
    """Build the context DTO for one canonical panel shape.

    ``none`` yields no DTO at all, so the reviewer builds no Context root.
    ``history_less`` carries one Session and one Turn item, which renders both
    scope groups without a History group. ``populated`` adds two of this
    session's own turn records, which the panel hoists into History and
    excludes from the scope groups.
    """
    if shape == "none":
        return None

    items = [
        _item(SESSION_ITEM_PATH, "Session", 1200),
        _item(TURN_ITEM_PATH, "Turn", 800),
    ]
    if shape == "populated":
        items.extend(
            [
                _item(HISTORY_PLAN_PATH, "Turn", 600),
                _item(HISTORY_REPORT_PATH, "Turn", 700),
            ]
        )

    return ProjectContext(
        header="Test Context",
        content="Test context content.",
        items=items,
        agent_name="Developer",
        system_prompt_tokens=4000,
        content_tokens=sum(item.token_count for item in items),
        total_window=200000,
        session_root=SESSION_ROOT,
    )
