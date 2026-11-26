import pytest
from textual.widgets import Input, Tree

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.outbound import IFileSystemManager, ISystemEnvironment

from tests.harness.drivers.tui_driver import TuiDriver


def _build_driver(env, plan: Plan, replacement: str) -> TuiDriver:
    """Builds a driver whose external-editor handovers carry ``replacement``."""
    return TuiDriver(
        plan,
        env.get_service(ISystemEnvironment),
        env.get_service(IFileSystemManager),
        mock_editor_output=replacement,
    )


async def _highlight_action_and_focus_parameters(pilot) -> None:
    """Walks the tree onto the first action, then focuses its parameter pane."""
    pilot.app.query_one(Tree).focus()
    await pilot.press("down", "down", "down")
    await pilot.pause()
    await pilot.press("tab")
    await pilot.pause()


async def _select_first_parameter(pilot) -> None:
    """Selects the first parameter row and lets the edit branch finish."""
    await pilot.press("enter")
    await pilot.pause()
    if len(pilot.app.screen_stack) > 1:
        # The inline modal opened instead of the editor. Close it so the worker
        # unblocks and the missing handover is what fails, not a hang.
        await pilot.press("escape")
        await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.anyio
async def test_multiline_parameter_opens_in_the_editor(env):
    """A query carrying newlines reaches the editor and keeps its line breaks."""
    query = "first line\nsecond line\nthird line"
    action = ActionData(type="RESEARCH", params={"queries": [query]}, selected=True)
    plan = Plan(title="Test", rationale="Test", actions=[action])
    driver = _build_driver(env, plan, replacement="edited first\nedited second")

    async with driver.app.run_test() as pilot:
        await _highlight_action_and_focus_parameters(pilot)
        assert driver.get_param_value(pilot, "queries") == query
        await _select_first_parameter(pilot)

    assert driver.editor_launch_suffixes == [".txt"]
    assert action.params["queries"] == ["edited first\nedited second"]


@pytest.mark.parametrize(
    ("original", "replacement", "expected"),
    [
        pytest.param(
            "echo one\necho two",
            "echo one\necho two\necho three\n",
            "echo one\necho two\necho three",
            id="one-appended-newline-stripped",
        ),
        pytest.param(
            "echo one\necho two\n",
            "echo one\necho two\n",
            "echo one\necho two\n",
            id="intentional-trailing-newline-preserved",
        ),
        pytest.param(
            "echo one\necho two",
            "echo three\r\n",
            "echo three",
            id="crlf-appended-newline-stripped",
        ),
        pytest.param("echo one\necho two", "", "", id="empty-result-clears"),
    ],
)
@pytest.mark.anyio
async def test_editor_result_is_applied_to_the_command(
    env, original: str, replacement: str, expected: str
):
    """The editor result lands in the command, minus one appended newline."""
    action = ActionData(type="EXECUTE", params={"command": original}, selected=True)
    plan = Plan(title="Test", rationale="Test", actions=[action])
    driver = _build_driver(env, plan, replacement=replacement)

    async with driver.app.run_test() as pilot:
        await _highlight_action_and_focus_parameters(pilot)
        await _select_first_parameter(pilot)

    assert driver.editor_launch_suffixes == [".txt"]
    assert action.params["command"] == expected


@pytest.mark.anyio
async def test_short_parameter_stays_in_the_inline_modal(env):
    """A short single-line command opens the modal and launches no editor."""
    action = ActionData(type="EXECUTE", params={"command": "echo hi"}, selected=True)
    plan = Plan(title="Test", rationale="Test", actions=[action])
    driver = _build_driver(env, plan, replacement="replaced")

    async with driver.app.run_test() as pilot:
        await _highlight_action_and_focus_parameters(pilot)
        await pilot.press("enter")
        await pilot.pause()
        pilot.app.screen.query_one("#param_input", Input).value = "echo bye"
        await pilot.press("enter")
        await pilot.pause()

    assert driver.editor_launch_suffixes == []
    assert action.params["command"] == "echo bye"
