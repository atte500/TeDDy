from typer.testing import CliRunner


from teddy_executor.main import app
from tests.acceptance.plan_builder import MarkdownPlanBuilder

runner = CliRunner()


def test_execute_action_report_shows_description():
    """
    Verify that the `EXECUTE` action log in the report includes
    the description from the plan.
    """
    plan = (
        MarkdownPlanBuilder("Test Plan")
        .add_action(
            "execute",
            {
                "Description": "My Test Command",
                "command": "echo 'hello'",
            },
        )
        .build()
    )

    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan],
        input="y\n",  # Approve the action
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert '#### `EXECUTE` on "My Test Command"' in result.stdout
