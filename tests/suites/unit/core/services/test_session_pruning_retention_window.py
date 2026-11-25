"""Unit coverage for the batched retention window.

Retention collects excess turn history in whole batches: nothing is pruned
until ``max_id - max_turns_retention`` reaches the configured batch, and then
the collected batch is dropped in one pass. The cut never passes
``max_id - max_turns_retention``, so the newest retention-limit turn positions
always survive, and a batch of one collapses to the per-turn cadence that
predates batching.

The file system double reports every path absent, which keeps failure-status
pruning inert so only the retention window shapes each result.
"""

import logging
from collections.abc import Mapping
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


@pytest.mark.parametrize("turn_count", [10, 11, 12, 13, 14])
def test_history_holds_while_the_excess_is_below_the_batch(turn_count):
    """With a limit of 10 and a batch of 5, the first four extra turns keep all."""
    context = _prune(sequential_turn_context(turn_count), limit=10)

    assert [item.selected for item in context.items] == [True] * turn_count
    assert [item.auto_prune_reason for item in context.items] == [None] * turn_count


def test_the_fifth_extra_turn_drops_the_collected_batch_of_five():
    """The fifteenth turn prunes ids 1-5 together and keeps the newest ten."""
    context = _prune(sequential_turn_context(15), limit=10)

    selected = _selected_by_path(context)
    assert [selected[turn_path(turn_id)] for turn_id in range(1, 16)] == (
        [False] * 5 + [True] * 10
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


def test_a_batch_beyond_the_excess_reserves_nothing():
    """Seven turns against a limit of 3 leave an excess of 4, short of the batch."""
    context = _prune(sequential_turn_context(7), limit=3)

    assert all(item.selected for item in context.items)


def test_the_collected_batch_never_eats_into_the_retention_floor():
    """Eight turns against a limit of 3 drop one batch of 5 and keep three."""
    context = _prune(sequential_turn_context(8), limit=3)

    selected = _selected_by_path(context)
    assert [selected[turn_path(turn_id)] for turn_id in range(1, 9)] == (
        [False] * 5 + [True] * 3
    )


def test_history_shorter_than_the_retention_limit_is_untouched():
    context = _prune(sequential_turn_context(3), limit=10)

    assert all(item.selected for item in context.items)


def test_a_gap_in_turn_ids_is_not_counted_as_a_pruned_turn():
    """An excess of 8 drops every id up to 6, which is three entries, not eight."""
    context = _prune(turn_context([1, 2, 5, 7, 10]), limit=2, batch=3)

    assert _selected_by_path(context) == {
        turn_path(1): False,
        turn_path(2): False,
        turn_path(5): False,
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
