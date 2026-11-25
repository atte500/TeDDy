"""Unit coverage for the retention ceiling.

``max_turns_retention`` is a ceiling on how many distinct turns the turn-scoped
context may hold, and ``retention_batch`` is how many of the oldest turns fall
together once that ceiling is exceeded. Past the ceiling, only the newest
``max(1, max_turns_retention - retention_batch + 1)`` turns survive, so the
retained history lands on that trough and holds there until the ceiling is
crossed again. A batch of one keeps the newest ``max_turns_retention`` turns,
reproducing the per-turn cadence that predates batching.

The file system double reports every path absent, which keeps failure-status
pruning inert so only the retention window shapes each result.
"""

import logging
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from unittest.mock import create_autospec

import pytest

from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from tests.harness.setup.pruning_scenarios import (
    sequential_turn_context,
    turn_context,
    turn_path,
)


class InMemoryConfigService(IConfigService):
    """A dictionary-backed configuration port, so a test names its settings."""

    def __init__(self, settings: Mapping[str, Any]):
        self._settings = dict(settings)

    def get_config_path(self) -> str:
        return ".teddy/config.yaml"

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self._settings[key] = value

    def set_env_variable(self, name: str, value: str) -> None:
        self._settings[f"env:{name}"] = value


def _no_turn_files() -> IFileSystemManager:
    """A file system where no turn artifact exists."""
    files = create_autospec(IFileSystemManager, instance=True)
    files.path_exists.return_value = False
    return files


def _prune(items: list[ContextItem], *, limit: int, batch: Any = 5) -> ProjectContext:
    """Run the outermost pruning entry point over ``items``.

    ``batch`` is handed to the read helper unparsed, so a test can pass a
    malformed setting exactly as a bad configuration would.
    """
    settings: dict[str, Any] = {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.turn_context_threshold": 0,
        "auto_pruning.max_turns_retention": limit,
        "auto_pruning.retention_batch": batch,
    }
    service = SessionPruningService(
        config_service=InMemoryConfigService(settings),
        file_system_manager=_no_turn_files(),
    )
    context = ProjectContext(items=items, header="", content="")
    return service.prune(context)


def _selected_by_path(context: ProjectContext) -> dict[str, bool]:
    return {item.path: item.selected for item in context.items}


@pytest.mark.parametrize("turn_count", [8, 9, 10])
def test_history_at_or_under_the_ceiling_is_untouched(turn_count):
    """A ceiling of 10 holds a history that never exceeds ten turns."""
    context = _prune(sequential_turn_context(turn_count), limit=10)

    assert [item.selected for item in context.items] == [True] * turn_count
    assert [item.auto_prune_reason for item in context.items] == [None] * turn_count


def test_the_first_turn_past_the_ceiling_drops_a_full_batch():
    """Eleven turns against a ceiling of 10 drop ids 1-5 and keep six."""
    context = _prune(sequential_turn_context(11), limit=10)

    selected = _selected_by_path(context)
    assert [selected[turn_path(turn_id)] for turn_id in range(1, 12)] == (
        [False] * 5 + [True] * 6
    )
    reasons = {item.auto_prune_reason for item in context.items if not item.selected}
    assert reasons == {"Turn exceeds retention limit of 10"}


@pytest.mark.parametrize("turn_count", [3, 4, 6])
def test_a_batch_of_one_reproduces_the_per_turn_cadence(turn_count):
    """The escape hatch keeps dropping one turn per boundary crossing."""
    context = _prune(sequential_turn_context(turn_count), limit=2, batch=1)

    selected = _selected_by_path(context)
    expected = [False] * (turn_count - 2) + [True] * 2
    assert [
        selected[turn_path(turn_id)] for turn_id in range(1, turn_count + 1)
    ] == expected


def test_a_batch_beyond_the_ceiling_keeps_the_newest_turn():
    """Seven turns against a ceiling of 3 clamp the retained count to one."""
    context = _prune(sequential_turn_context(7), limit=3, batch=5)

    selected = _selected_by_path(context)
    assert [selected[turn_path(turn_id)] for turn_id in range(1, 8)] == (
        [False] * 6 + [True]
    )


def test_an_overage_larger_than_the_batch_lands_on_the_trough():
    """Eight turns against a ceiling of 3 and a batch of 2 keep the newest two."""
    context = _prune(sequential_turn_context(8), limit=3, batch=2)

    selected = _selected_by_path(context)
    assert [selected[turn_path(turn_id)] for turn_id in range(1, 9)] == (
        [False] * 6 + [True] * 2
    )


def test_history_shorter_than_the_retention_limit_is_untouched():
    context = _prune(sequential_turn_context(3), limit=10)

    assert all(item.selected for item in context.items)


def test_a_gap_in_turn_ids_does_not_inflate_the_ceiling():
    """Five turns spread to id 10 drop the two oldest and keep the newest three."""
    context = _prune(turn_context([1, 2, 5, 7, 10]), limit=4, batch=2)

    assert _selected_by_path(context) == {
        turn_path(1): False,
        turn_path(2): False,
        turn_path(5): True,
        turn_path(7): True,
        turn_path(10): True,
    }


@pytest.mark.parametrize("bad_batch", [0, -4, "five"])
def test_a_bad_batch_falls_back_to_one_with_a_warning(bad_batch, caplog):
    """A bad setting must not silently disable retention."""
    with caplog.at_level(logging.WARNING):
        context = _prune(sequential_turn_context(4), limit=2, batch=bad_batch)

    selected = _selected_by_path(context)
    assert [selected[turn_path(turn_id)] for turn_id in range(1, 5)] == [
        False,
        False,
        True,
        True,
    ]
    assert any("retention_batch" in message for message in caplog.messages)


def test_retention_disabled_leaves_every_turn_selected():
    """A ceiling of 0 disables retention, so a long history survives untouched."""
    context = _prune(sequential_turn_context(12), limit=0)

    assert all(item.selected for item in context.items)
    assert all(item.auto_prune_reason is None for item in context.items)


def test_pruning_twice_deselects_nothing_further():
    """The second pass finds the history on the trough, so it changes nothing."""
    first = _prune(sequential_turn_context(11), limit=10)

    second = _prune(list(first.items), limit=10)

    assert [(item.selected, item.auto_prune_reason) for item in second.items] == [
        (item.selected, item.auto_prune_reason) for item in first.items
    ]


def test_a_turn_already_deselected_keeps_its_reason_and_the_newest_six():
    """A turn dropped by another heuristic holds no context, so it neither
    counts against the ceiling nor earns a retention reason."""
    items = sequential_turn_context(12)
    items[0] = replace(
        items[0], selected=False, auto_prune_reason="Plan failed validation"
    )

    context = _prune(items, limit=10)

    assert _selected_by_path(context) == {
        turn_path(turn_id): turn_id >= 7 for turn_id in range(1, 13)
    }
    assert context.items[0].auto_prune_reason == "Plan failed validation"
    assert {
        item.auto_prune_reason for item in context.items[1:] if not item.selected
    } == {"Turn exceeds retention limit of 10"}
