"""Reviewer ``e`` behaviour on context nodes.

The context panel is the surface a reviewer consults before approving a plan, so
``e`` opens the manifest or file a node names instead of doing nothing. The
System row opens the persona picker instead, and the toggle binding must survive
untouched.
"""

import pytest

from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    CONTEXT_ROOT,
    SESSION_LABEL,
    SYSTEM_LABEL,
    TURN_LABEL,
)
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)
from teddy_executor.core.ports.outbound import IFileSystemManager, ISystemEnvironment

from tests.harness.drivers.tui_driver import TuiDriver

EDITOR_REPLACEMENT = "# opened in place\n"


def _item(path: str, scope: str = "Session") -> ContextItem:
    return ContextItem(path=path, token_count=120, git_status="M", scope=scope)


def _panel(session_root: str, items: list[ContextItem]) -> ProjectContext:
    return ProjectContext(
        header="Test Header",
        content="Test Content",
        items=items,
        agent_name="Developer",
        system_prompt_tokens=4000,
        content_tokens=sum(item.token_count for item in items),
        total_window=200000,
        session_root=session_root,
    )


def _plan(plan_path: str | None = None) -> Plan:
    return Plan(
        title="Context actions",
        rationale="R",
        actions=[ActionData(type="READ", params={"resource": "README.md"})],
        plan_path=plan_path,
    )


def _driver(env, panel: ProjectContext, plan: Plan | None = None) -> TuiDriver:
    return TuiDriver(
        plan or _plan(),
        env.get_service(ISystemEnvironment),
        env.get_service(IFileSystemManager),
        project_context=panel,
    )


def _record_notifications(app) -> list[str]:
    """Captures the app's user-facing notifications in order."""
    messages: list[str] = []
    app.notify = lambda message, **_: messages.append(message)
    return messages


async def _park_cursor(driver: TuiDriver, pilot, matches) -> None:
    """Expand the Context root and park the cursor on the node that matches.

    The reviewer builds the Context root collapsed, so its children carry no
    render line until it expands. Parking the cursor without expanding lands on
    no node at all, which the gate reports as a disabled binding rather than as
    a navigation mistake — hence the assertion.
    """
    driver.find_node(pilot, lambda data: data == CONTEXT_ROOT).expand()
    await pilot.pause()
    node = driver.find_node(pilot, matches)
    driver.tree(pilot).move_cursor(node)
    await pilot.pause()
    assert driver.tree(pilot).cursor_node is node, "cursor did not land on the row"


async def _press_e_on(driver: TuiDriver, pilot, matches) -> None:
    await _park_cursor(driver, pilot, matches)
    await pilot.press("e")
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.anyio
async def test_session_label_opens_the_session_manifest(env, tmp_path, monkeypatch):
    """The Session label opens ``session.context`` in place, without confirming."""
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", EDITOR_REPLACEMENT)
    session_root = tmp_path / "session"
    session_root.mkdir()
    manifest = session_root / "session.context"
    manifest.write_text("ORIGINAL\n", encoding="utf-8")
    driver = _driver(env, _panel(session_root.as_posix(), [_item("src/app.py")]))

    async with driver.interaction() as pilot:
        await _press_e_on(driver, pilot, lambda data: data == SESSION_LABEL)

    assert manifest.read_text(encoding="utf-8") == EDITOR_REPLACEMENT


@pytest.mark.anyio
async def test_file_row_opens_the_named_file(env, tmp_path, monkeypatch):
    """A context file row opens that file in place, in the same turn."""
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", EDITOR_REPLACEMENT)
    target = tmp_path / "notes.md"
    target.write_text("ORIGINAL\n", encoding="utf-8")
    driver = _driver(
        env,
        _panel((tmp_path / "session").as_posix(), [_item(target.as_posix())]),
    )

    async with driver.interaction() as pilot:
        await _press_e_on(driver, pilot, lambda data: isinstance(data, ContextItem))

    assert target.read_text(encoding="utf-8") == EDITOR_REPLACEMENT


@pytest.mark.anyio
async def test_edit_details_is_enabled_only_on_openable_context_nodes(env, tmp_path):
    """Session, Turn, file, and System rows all accept ``e``."""
    driver = _driver(
        env,
        _panel(
            (tmp_path / "session").as_posix(),
            [_item("src/app.py", "Session"), _item("docs/project/PROJECT.md", "Turn")],
        ),
    )

    async with driver.interaction() as pilot:
        await _park_cursor(driver, pilot, lambda data: isinstance(data, ContextItem))
        assert pilot.app.check_action("edit_details", ()) is True
        assert pilot.app.check_action("toggle_selection", ()) is True

        for payload in (SESSION_LABEL, TURN_LABEL):
            await _park_cursor(driver, pilot, lambda data, p=payload: data == p)
            assert pilot.app.check_action("edit_details", ()) is True

        await _park_cursor(driver, pilot, lambda data: data == SYSTEM_LABEL)
        assert pilot.app.check_action("edit_details", ()) is True


@pytest.mark.anyio
async def test_missing_session_manifest_notifies_instead_of_opening(
    env, tmp_path, monkeypatch
):
    """A blank editor must not stand in for a manifest that does not exist."""
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", EDITOR_REPLACEMENT)
    session_root = tmp_path / "session"
    session_root.mkdir()
    driver = _driver(env, _panel(session_root.as_posix(), [_item("src/app.py")]))
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e_on(driver, pilot, lambda data: data == SESSION_LABEL)

    assert notifications == [
        f"Session manifest not found: {(session_root / 'session.context').as_posix()}"
    ]
    assert not (session_root / "session.context").exists()


@pytest.mark.anyio
async def test_turn_label_notifies_when_the_turn_directory_is_unknown(
    env, tmp_path, monkeypatch
):
    """A ``--plan-content`` run names no turn directory, so ``e`` must say so."""
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", EDITOR_REPLACEMENT)
    driver = _driver(
        env,
        _panel((tmp_path / "session").as_posix(), [_item("src/app.py", "Turn")]),
        plan=_plan(plan_path=None),
    )
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e_on(driver, pilot, lambda data: data == TURN_LABEL)

    assert notifications == ["Turn context is unavailable for this plan."]


@pytest.mark.anyio
async def test_pruned_context_file_notifies_with_its_path(env, tmp_path, monkeypatch):
    """A context entry can outlive the file it names, so ``e`` reports the path."""
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", EDITOR_REPLACEMENT)
    pruned = tmp_path / "pruned.md"
    driver = _driver(
        env,
        _panel((tmp_path / "session").as_posix(), [_item(pruned.as_posix())]),
    )
    notifications = _record_notifications(driver.app)

    async with driver.interaction() as pilot:
        await _press_e_on(driver, pilot, lambda data: isinstance(data, ContextItem))

    assert notifications == [f"Context file not found: {pruned.as_posix()}"]
    assert not pruned.exists()
