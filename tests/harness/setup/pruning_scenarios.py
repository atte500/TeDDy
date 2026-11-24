"""Canonical pruning retention scenarios for batch-boundary tests.

Retention pruning classifies ``ContextItem`` values by the turn id encoded in
the path, so a run of items with sequential ids drives every batch boundary by
construction. These scenarios build that run without a real session, so a
pruning test reads one builder instead of inventing turn directories.

The module is data only: it imports no pruning-service code, so a test cannot
couple to the implementation it exercises.
"""

from collections.abc import Iterable

from teddy_executor.core.domain.models.project_context import ContextItem

TURN_ROOT = ".teddy/sessions/retention-scenario"
TURN_TOKEN_COUNT = 100


def turn_path(turn_id: int) -> str:
    """The canonical Turn-scoped path carrying ``turn_id`` in its directory."""
    return f"{TURN_ROOT}/{turn_id:02d}/plan.md"


def turn_context(turn_ids: Iterable[int]) -> list[ContextItem]:
    """Build one Turn-scoped item per id, preserving the given order.

    Explicit ids let a test express a gap, because the retention heuristic
    counts turn ids rather than items.
    """
    return [
        ContextItem(
            path=turn_path(turn_id),
            token_count=TURN_TOKEN_COUNT,
            git_status="  ",
            scope="Turn",
        )
        for turn_id in turn_ids
    ]


def sequential_turn_context(turn_count: int, start: int = 1) -> list[ContextItem]:
    """Build ``turn_count`` consecutive turns, ids ``start`` upward."""
    return turn_context(range(start, start + turn_count))
