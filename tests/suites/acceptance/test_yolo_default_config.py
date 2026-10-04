"""Acceptance tests for the configurable ``yolo_default`` feature.

Drives the CLI in-process (Subcutaneous Testing) to prove the tri-state
``--yolo`` / ``--no-yolo`` (``-y`` / ``-n``) flag resolves end-to-end.
"""

import pytest

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment


def _create_plan() -> str:
    return (
        MarkdownPlanBuilder("YOLO tri-state")
        .add_create("test.txt", "content", description="Make file")
        .build()
    )


@pytest.mark.parametrize("flag", ["-n", "--no-yolo"])
def test_execute_no_yolo_flag_is_accepted_and_runs_interactively(
    tmp_path, monkeypatch, flag
):
    """Scenario: ``execute --no-yolo`` / ``-n`` is accepted and runs interactively.

    The tri-state flag exposes ``--no-yolo`` / ``-n`` as the explicit
    interactive override. Passing it must be accepted (previously an unknown
    option) and must prompt the user for each action.
    """
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    result = adapter.run_execute_with_plan(
        _create_plan(), input="y\n", interactive=True, extra_args=[flag]
    )

    assert result.exit_code == 0
    output = result.stdout + result.stderr
    assert "Action: CREATE" in output
