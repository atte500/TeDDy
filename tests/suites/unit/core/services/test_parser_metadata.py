import os
import pytest
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def parser(container) -> IPlanParser:
    return container.resolve(IPlanParser)


def _p(parser, builder):
    return parser.parse(builder.build())


def test_parse_execute_action_with_allow_failure(parser: IPlanParser):
    """Verify Allow Failure metadata is correctly extracted."""
    builder = MarkdownPlanBuilder("T").add_execute("pytest", allow_failure=True)
    action = _p(parser, builder).actions[0]
    assert action.params.get("allow_failure") is True
    assert action.params["command"] == "pytest"


def test_parse_execute_action_with_background(parser: IPlanParser):
    """Verify Background: true is extracted as a boolean."""
    builder = MarkdownPlanBuilder("T").add_execute(
        "python -m http.server", background=True
    )
    action = _p(parser, builder).actions[0]
    assert action.params.get("background") is True


def test_parse_execute_action_with_background_false(parser: IPlanParser):
    """Verify Background: false is extracted as a boolean."""
    builder = MarkdownPlanBuilder("T").add_execute("ls", background=False)
    action = _p(parser, builder).actions[0]
    assert action.params.get("background") is False


def test_parse_execute_action_with_timeout(parser: IPlanParser):
    """Verify Timeout is extracted as an integer."""
    expected_timeout = 120
    builder = MarkdownPlanBuilder("T").add_execute("sleep 10", timeout=expected_timeout)
    action = _p(parser, builder).actions[0]
    assert action.params.get("timeout") == expected_timeout


def test_parse_execute_action_with_invalid_timeout(parser: IPlanParser):
    """Verify invalid Timeout remains as a string."""
    builder = MarkdownPlanBuilder("T").add_execute("ls", timeout="abc")
    action = _p(parser, builder).actions[0]
    assert action.params.get("timeout") == "abc"


def test_parse_execute_action_with_cd_directive(parser: IPlanParser):
    """Verify 'cd' lines remain in the command."""
    cmd = "cd src/my_dir\npoetry run pytest"
    builder = MarkdownPlanBuilder("T").add_execute(cmd)
    action = _p(parser, builder).actions[0]
    assert action.params["command"] == cmd


def test_parse_execute_action_with_export_directive(parser: IPlanParser):
    """Verify 'export' lines remain in the command."""
    cmd = "export FOO=bar\nexport BAZ=\"qux\"\nexport OTHER='single_quotes'\nmy_command --do-something"
    builder = MarkdownPlanBuilder("T").add_execute(cmd)
    action = _p(parser, builder).actions[0]
    assert action.params["command"] == cmd


def test_parse_execute_action_with_mixed_directives(parser: IPlanParser):
    """Verify mixed directives remain in the command."""
    cmd = 'cd tests\nexport CI=true\n\npytest -k "my_test"'
    builder = MarkdownPlanBuilder("T").add_execute(cmd)
    action = _p(parser, builder).actions[0]
    assert action.params["command"] == cmd


def test_parse_read_action_with_absolute_path(parser):
    """Verify absolute paths are preserved and normalized to POSIX."""
    absolute_path = "C:\\test.txt" if os.name == "nt" else "/tmp/test.txt"
    # Note: Use path directly to avoid builder adding leading slash to Windows absolute paths
    builder = MarkdownPlanBuilder("T").add_read(absolute_path)
    action = _p(parser, builder).actions[0]
    assert action.params["resource"] == absolute_path.replace("\\", "/")
