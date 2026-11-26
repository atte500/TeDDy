"""Unit coverage for the cost-of-loss order of the global budget.

The budget deselects Turn-scope files until their total fits
``auto_pruning.turn_context_threshold``. Ranking victims by size alone put a
turn record, which nothing re-renders, in competition with a copy of a project
file that one READ restores. A copy therefore leaves first, largest-first
inside that class, and only once no copy remains does the oldest retained turn
leave with its whole record set.

The file system double reports every path absent, which keeps validation
pruning inert so the budget alone shapes each result.
"""

from unittest.mock import create_autospec

from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.services.session_pruning_service import SessionPruningService

BUDGET_SESSION_ROOT = ".teddy/sessions/budget-scenario"


def _record(turn_id: int, name: str, tokens: int) -> ContextItem:
    """A plan or report inside a numeric turn directory."""
    return ContextItem(
        path=f"{BUDGET_SESSION_ROOT}/{turn_id:02d}/{name}",
        token_count=tokens,
        git_status="  ",
        scope="Turn",
    )


def _copy(path: str, tokens: int) -> ContextItem:
    """A restorable copy of a project file."""
    return ContextItem(path=path, token_count=tokens, git_status="  ", scope="Turn")


def _prune(items: list[ContextItem], threshold: int) -> ProjectContext:
    """Run the outermost pruning entry point with only the budget armed."""
    settings = {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.turn_context_threshold": threshold,
    }
    config = create_autospec(IConfigService, instance=True)
    config.get_setting.side_effect = lambda key, default=None: settings.get(
        key, default
    )
    files = create_autospec(IFileSystemManager, instance=True)
    files.path_exists.return_value = False
    service = SessionPruningService(config_service=config, file_system_manager=files)
    return service.prune(ProjectContext(items=items, header="", content=""))


def _selected(context: ProjectContext) -> dict[str, bool]:
    return {item.path: item.selected for item in context.items}


def test_a_copy_leaves_before_a_larger_record():
    """The 400-token copy leaves while the 900-token plan it outlived stays."""
    plan = _record(1, "plan.md", 900)
    copy = _copy("src/huge_module.py", 400)

    context = _prune([plan, copy], threshold=1000)

    selected = _selected(context)
    assert selected["src/huge_module.py"] is False
    assert selected[plan.path] is True


def test_whole_turns_leave_oldest_first_when_copies_run_out():
    """Records alone exceed the budget, so the oldest turns go before the newest."""
    turn1 = _record(1, "plan.md", 300)
    turn2 = _record(2, "plan.md", 300)
    turn3 = _record(3, "plan.md", 400)

    context = _prune([turn1, turn2, turn3], threshold=500)

    selected = _selected(context)
    assert selected[turn1.path] is False
    assert selected[turn2.path] is False
    assert selected[turn3.path] is True


def test_a_turns_plan_and_report_leave_together():
    """A record pair never parts company while the budget needs room."""
    plan1 = _record(1, "plan.md", 400)
    report1 = _record(1, "report.md", 400)
    plan2 = _record(2, "plan.md", 100)

    context = _prune([plan1, report1, plan2], threshold=500)

    selected = _selected(context)
    assert selected[plan1.path] is False
    assert selected[report1.path] is False
    assert selected[plan2.path] is True


def test_a_turn_holding_only_one_record_drops_just_that_one():
    """A manifest can carry a report without its plan, so no pair is assumed."""
    lone_report = _record(1, "report.md", 300)
    plan2 = _record(2, "plan.md", 500)

    context = _prune([lone_report, plan2], threshold=500)

    selected = _selected(context)
    assert selected[lone_report.path] is False
    assert selected[plan2.path] is True


def test_a_project_file_named_plan_md_outside_a_turn_directory_stays_a_copy():
    """Only a plan or report under a numeric turn directory counts as a record."""
    report = _record(1, "report.md", 500)
    docs_plan = _copy("docs/plan.md", 500)

    context = _prune([report, docs_plan], threshold=600)

    selected = _selected(context)
    assert selected["docs/plan.md"] is False
    assert selected[report.path] is True


def test_equal_sizes_keep_manifest_order():
    """Two equally large copies keep their manifest order, largest-first aside."""
    first = _copy("src/first.py", 500)
    second = _copy("src/second.py", 500)

    context = _prune([first, second], threshold=600)

    selected = _selected(context)
    assert selected["src/first.py"] is False
    assert selected["src/second.py"] is True
