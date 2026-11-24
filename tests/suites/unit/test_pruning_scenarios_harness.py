"""Contract tests for the canonical pruning retention scenarios.

Retention pruning classifies ``ContextItem`` values by the turn id encoded in
their path, so a run of items with sequential ids drives every batch boundary
by construction. These tests pin the shape the scenarios promise: one
Turn-scoped item per id, zero-padded paths the production extractor reads back
as the same id, declaration order preserved, and gaps honoured as gaps.
"""

from unittest.mock import create_autospec

import pytest

from teddy_executor.core.domain.models.project_context import ContextItem
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from tests.harness.setup.pruning_scenarios import (
    TURN_TOKEN_COUNT,
    sequential_turn_context,
    turn_context,
    turn_path,
)


@pytest.fixture
def extract_turn_id():
    """The production turn-id extractor, so the fixture cannot drift from it."""
    service = SessionPruningService(
        config_service=create_autospec(IConfigService, instance=True),
        file_system_manager=create_autospec(IFileSystemManager, instance=True),
    )
    return service._extract_turn_id


def test_turn_path_is_zero_padded_under_the_turn_root():
    assert turn_path(1) == ".teddy/sessions/retention-scenario/01/plan.md"
    assert turn_path(12).endswith("/12/plan.md")


def test_sequential_context_builds_one_item_per_id(extract_turn_id):
    items = sequential_turn_context(5)

    assert [extract_turn_id(item.path) for item in items] == [
        "01",
        "02",
        "03",
        "04",
        "05",
    ]


def test_every_built_item_is_a_selected_turn_scope_item():
    item = sequential_turn_context(1)[0]

    assert isinstance(item, ContextItem)
    assert item.scope == "Turn"
    assert item.selected is True
    assert item.auto_prune_reason is None
    assert item.token_count == TURN_TOKEN_COUNT


def test_sequential_context_honours_a_start_offset(extract_turn_id):
    items = sequential_turn_context(3, start=9)

    assert [extract_turn_id(item.path) for item in items] == ["09", "10", "11"]


def test_turn_context_preserves_explicit_sparse_ids(extract_turn_id):
    items = turn_context([1, 2, 5, 7])

    assert [extract_turn_id(item.path) for item in items] == [
        "01",
        "02",
        "05",
        "07",
    ]


def test_empty_builds_nothing():
    assert sequential_turn_context(0) == []
    assert turn_context([]) == []
