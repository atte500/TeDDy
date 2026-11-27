"""Reviewer persona switching from the System node.

``e`` on the System row opens the persona picker, marks the active persona, and
reports the picked one. Every failure is reported rather than raised: switching
needs a roster and a session to persist into, and ``ReviewerApp`` is built at
many call sites that hold neither handle.
"""

from typing import Any

import pytest
from textual.widgets import Label, ListItem, ListView

from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    CONTEXT_ROOT,
    SYSTEM_LABEL,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    AGENT_CURRENT_MARKER,
    AgentSelectScreen,
)
from teddy_executor.core.domain.models.exceptions import AgentCatalogError
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)
from teddy_executor.core.ports.outbound import (
    IFileSystemManager,
    ISessionManager,
    ISystemEnvironment,
)

from tests.harness.drivers.tui_driver import TuiDriver
from tests.harness.setup.fake_agent_catalog import FakeAgentCatalog
from tests.harness.setup.mocking import spec_mock

ROSTER = ("Pathfinder", "Developer")
_ABSENT = object()


def _plan() -> Plan:
    return Plan(
        title="Agent switch",
        rationale="R",
        actions=[ActionData(type="READ", params={"resource": "README.md"})],
    )


def _panel(session_root: str | None) -> ProjectContext:
    items = [
        ContextItem(path="src/app.py", token_count=120, git_status="M", scope="Session")
    ]
    return ProjectContext(
        header="Test Header",
        content="Test Content",
        items=items,
        agent_name="Pathfinder",
        system_prompt_tokens=4000,
        content_tokens=sum(item.token_count for item in items),
        total_window=200000,
        session_root=session_root,
    )


def _driver(
    env,
    tmp_path,
    *,
    catalog: Any = _ABSENT,
    session_manager: Any = _ABSENT,
    session_in_scope: bool = True,
) -> TuiDriver:
    """Builds a reviewer driver whose persona-switch handles stay injectable."""
    return TuiDriver(
        _plan(),
        env.get_service(ISystemEnvironment),
        env.get_service(IFileSystemManager),
        project_context=_panel(
            (tmp_path / "session").as_posix() if session_in_scope else None
        ),
        agent_catalog=(
            FakeAgentCatalog(agents=ROSTER) if catalog is _ABSENT else catalog
        ),
        session_manager=(
            spec_mock(ISessionManager)
            if session_manager is _ABSENT
            else session_manager
        ),
    )


def _record_notifications(app) -> list[str]:
    """Captures the app's user-facing notifications in order."""
    messages: list[str] = []
    app.notify = lambda message, **_: messages.append(message)
    return messages


async def _park_cursor(driver: TuiDriver, pilot, matches) -> None:
    """Expand the Context root and park the cursor on the node that matches."""
    driver.find_node(pilot, lambda data: data == CONTEXT_ROOT).expand()
    await pilot.pause()
    node = driver.find_node(pilot, matches)
    driver.tree(pilot).move_cursor(node)
    await pilot.pause()
    assert driver.tree(pilot).cursor_node is node, "cursor did not land on the row"


async def _press_e(driver: TuiDriver, pilot, matches) -> None:
    """Park the cursor on a System row and press ``e``.

    The picker is pushed synchronously, so no worker wait follows: a modal's own
    workers are blocked on its dismissal.
    """
    await _park_cursor(driver, pilot, matches)
    await pilot.press("e")
    await pilot.pause()


def _is_persona_leaf(data: Any) -> bool:
    return isinstance(data, dict) and data.get("type") == "SYSTEM_PROMPT"


@pytest.mark.anyio
async def test_system_row_opens_the_picker_marking_the_current_persona(env, tmp_path):
    """The picker states the roster and marks the persona already in force."""
    driver = _driver(env, tmp_path)

    async with driver.interaction() as pilot:
        await _press_e(driver, pilot, lambda data: data == SYSTEM_LABEL)
        screen = pilot.app.screen

        assert isinstance(screen, AgentSelectScreen)
        assert screen.agents == ROSTER
        assert screen.current == "Pathfinder"
        assert screen.query_one(ListView).index == 0
        labels = [str(item.query_one(Label).content) for item in screen.query(ListItem)]
        assert labels == [f"Pathfinder {AGENT_CURRENT_MARKER}", "Developer"]


@pytest.mark.anyio
async def test_picking_a_persona_reports_the_selection(env, tmp_path):
    """The picked persona crosses the dismissal boundary and closes the picker."""
    driver = _driver(env, tmp_path)
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e(driver, pilot, lambda data: data == SYSTEM_LABEL)
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        assert not isinstance(pilot.app.screen, AgentSelectScreen)

    assert notifications == ["Selected agent: Developer"]


@pytest.mark.anyio
async def test_dismissed_picker_changes_nothing(env, tmp_path):
    """An abandoned selection is inert: no persona is reported."""
    driver = _driver(env, tmp_path)
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e(driver, pilot, lambda data: data == SYSTEM_LABEL)
        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(pilot.app.screen, AgentSelectScreen)

    assert notifications == []


@pytest.mark.anyio
async def test_empty_roster_notifies_and_opens_no_picker(env, tmp_path):
    """A workspace with no prompt file offers no name the planner could load."""
    driver = _driver(env, tmp_path, catalog=FakeAgentCatalog(agents=()))
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e(driver, pilot, lambda data: data == SYSTEM_LABEL)
        assert not isinstance(pilot.app.screen, AgentSelectScreen)

    assert notifications == ["No agent personas are installed."]


@pytest.mark.anyio
async def test_unreadable_roster_notifies_instead_of_escaping(env, tmp_path):
    """A listing failure is reported, never rendered as an empty roster."""
    driver = _driver(
        env,
        tmp_path,
        catalog=FakeAgentCatalog(error=AgentCatalogError("roster unreadable")),
    )
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e(driver, pilot, lambda data: data == SYSTEM_LABEL)
        assert not isinstance(pilot.app.screen, AgentSelectScreen)

    assert notifications == ["Could not list agent personas: roster unreadable"]


@pytest.mark.anyio
async def test_no_session_in_scope_notifies_and_opens_no_picker(env, tmp_path):
    """A switch persists into a session, so the picker never invents one."""
    driver = _driver(env, tmp_path, session_in_scope=False)
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e(driver, pilot, lambda data: data == SYSTEM_LABEL)
        assert not isinstance(pilot.app.screen, AgentSelectScreen)

    assert notifications == ["No session in scope."]


@pytest.mark.anyio
@pytest.mark.parametrize("absent", ["catalog", "session_manager"])
async def test_absent_handles_notify_instead_of_raising(env, tmp_path, absent):
    """An optional handle that is absent reports rather than crashing the reviewer."""
    driver = _driver(env, tmp_path, **{absent: None})
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e(driver, pilot, lambda data: data == SYSTEM_LABEL)
        assert not isinstance(pilot.app.screen, AgentSelectScreen)

    assert notifications == ["Agent switching is unavailable in this reviewer."]


@pytest.mark.anyio
async def test_edit_details_is_enabled_on_the_system_rows(env, tmp_path):
    """Both the System row and its persona leaf accept ``e``."""
    driver = _driver(env, tmp_path)

    async with driver.interaction() as pilot:
        await _park_cursor(driver, pilot, lambda data: data == SYSTEM_LABEL)
        assert pilot.app.check_action("edit_details", ()) is True

        await _park_cursor(driver, pilot, _is_persona_leaf)
        assert pilot.app.check_action("edit_details", ()) is True
