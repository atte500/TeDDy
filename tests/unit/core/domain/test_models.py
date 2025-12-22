import pytest

from teddy.core.domain.models import (
    CommandResult,
    Plan,
    ActionResult,
    ExecutionReport,
    ExecuteAction,
    CreateFileAction,
    ReadAction,
    EditAction,
    ChatWithUserAction,
    FileAlreadyExistsError,
)


def test_command_result_instantiation():
    """
    Tests that a CommandResult can be instantiated with valid data.
    """
    result = CommandResult(stdout="output", stderr="error", return_code=1)
    assert result.stdout == "output"
    assert result.stderr == "error"
    assert result.return_code == 1


class TestExecuteAction:
    def test_instantiation_happy_path(self):
        """Tests happy path instantiation for ExecuteAction."""
        action = ExecuteAction(command="ls -l")
        assert action.command == "ls -l"
        assert action.action_type == "execute"

    def test_instantiation_with_empty_command_raises_error(self):
        """Tests that an empty command raises a ValueError."""
        with pytest.raises(ValueError, match="'command' parameter cannot be empty"):
            ExecuteAction(command=" ")

    def test_instantiation_with_non_string_command_raises_error(self):
        """Tests that a non-string command raises a ValueError."""
        with pytest.raises(ValueError, match="'command' parameter cannot be empty"):
            ExecuteAction(command=123)


class TestCreateFileAction:
    def test_instantiation_happy_path(self):
        """Tests happy path instantiation for CreateFileAction."""
        action = CreateFileAction(file_path="path/to/file.txt", content="Hello")
        assert action.file_path == "path/to/file.txt"
        assert action.content == "Hello"
        assert action.action_type == "create_file"

    def test_missing_content_defaults_to_empty_string(self):
        """Tests that missing content defaults to an empty string."""
        action = CreateFileAction(file_path="path/to/file.txt")
        assert action.content == ""

    def test_empty_file_path_raises_error(self):
        """Tests that an empty file_path raises a ValueError."""
        with pytest.raises(ValueError, match="'file_path' parameter cannot be empty"):
            CreateFileAction(file_path=" ")

    def test_non_string_file_path_raises_error(self):
        """Tests that a non-string file_path raises a ValueError."""
        with pytest.raises(ValueError, match="'file_path' parameter cannot be empty"):
            CreateFileAction(file_path=123)


class TestReadAction:
    def test_instantiation_happy_path(self):
        """Tests happy path instantiation for ReadAction."""
        action = ReadAction(source="path/to/file.txt")
        assert action.source == "path/to/file.txt"
        assert action.action_type == "read"

    def test_empty_source_raises_error(self):
        """Tests that an empty source raises a ValueError."""
        with pytest.raises(ValueError, match="'source' parameter cannot be empty"):
            ReadAction(source=" ")

    def test_non_string_source_raises_error(self):
        """Tests that a non-string source raises a ValueError."""
        with pytest.raises(ValueError, match="'source' parameter cannot be empty"):
            ReadAction(source=123)

    @pytest.mark.parametrize(
        "source, expected",
        [
            ("http://example.com", True),
            ("https://example.com", True),
            ("HTTP://EXAMPLE.COM", True),
            ("ftp://example.com", False),
            ("path/to/file.txt", False),
            ("/abs/path/to/file.txt", False),
            ("C:\\windows\\path.txt", False),
        ],
    )
    def test_is_remote(self, source, expected):
        """Tests the is_remote() method correctly identifies URLs."""
        action = ReadAction(source=source)
        assert action.is_remote() is expected


def test_plan_raises_error_on_empty_actions_list():
    """
    Tests that a Plan cannot be instantiated with an empty list of actions.
    """
    with pytest.raises(ValueError, match="Plan must contain at least one action"):
        Plan(actions=[])


def test_action_result_raises_error_on_invalid_status():
    """
    Tests that ActionResult raises a ValueError on an invalid status.
    """
    action = ExecuteAction(command="test")
    with pytest.raises(ValueError, match="Status must be one of"):
        ActionResult(action=action, status="INVALID_STATUS")


def test_action_result_instantiation():
    """
    Tests that an ActionResult can be instantiated with valid data.
    """
    action = ExecuteAction(command="test")
    result = ActionResult(action=action, status="SUCCESS", output="some output")
    assert result.action == action
    assert result.status == "SUCCESS"
    assert result.output == "some output"
    assert result.error is None


def test_execution_report_instantiation():
    """
    Tests that an ExecutionReport can be instantiated with valid data.
    """
    report = ExecutionReport(
        run_summary={"status": "SUCCESS"},
        environment={"os": "test_os"},
        action_logs=[
            ActionResult(
                action=ExecuteAction(command="test"), status="SUCCESS", output="ok"
            )
        ],
    )
    assert report.run_summary == {"status": "SUCCESS"}
    assert report.environment == {"os": "test_os"}
    assert len(report.action_logs) == 1


def test_plan_instantiation():
    """
    Tests that a Plan can be instantiated with a list of actions.
    """
    actions = [ExecuteAction(command="ls")]
    plan = Plan(actions=actions)
    assert plan.actions == actions


def test_action_result_can_represent_failure():
    """
    Tests that ActionResult can be instantiated to represent a failed action.
    """
    failed_action = CreateFileAction(file_path="/test/file.txt")
    error_message = "File already exists"
    result = ActionResult(action=failed_action, status="FAILURE", error=error_message)

    assert result.action == failed_action
    assert result.status == "FAILURE"
    assert result.error == error_message
    assert result.output is None


def test_file_already_exists_error_stores_path():
    """
    Tests that the FileAlreadyExistsError custom exception correctly stores the file path.
    """
    path = "/path/to/some/file.txt"
    message = "File already exists"
    try:
        raise FileAlreadyExistsError(message, file_path=path)
    except FileAlreadyExistsError as e:
        assert str(e) == message
        assert e.file_path == path


def test_multiple_matches_found_error_can_be_raised_and_stores_content():
    """
    Tests that the MultipleMatchesFoundError custom exception can be raised
    and correctly stores the original content.
    """
    from teddy.core.domain.models import MultipleMatchesFoundError

    original_content = "some original content"
    message = "Test error message"
    try:
        raise MultipleMatchesFoundError(message, content=original_content)
    except MultipleMatchesFoundError as e:
        assert str(e) == message
        assert e.content == original_content


class TestEditAction:
    def test_instantiation_happy_path(self):
        """Tests happy path instantiation for EditAction."""
        action = EditAction(file_path="path/to/file.txt", find="old", replace="new")
        assert action.file_path == "path/to/file.txt"
        assert action.find == "old"
        assert action.replace == "new"
        assert action.action_type == "edit"

    def test_instantiation_with_empty_find_is_allowed(self):
        """Tests that an empty 'find' string is allowed."""
        action = EditAction(file_path="path/to/file.txt", find="", replace="new stuff")
        assert action.find == ""

    def test_instantiation_with_empty_replace_is_allowed(self):
        """Tests that an empty 'replace' string is allowed for deletion."""
        try:
            EditAction(file_path="path/to/file.txt", find="old", replace="")
        except (ValueError, TypeError) as e:
            pytest.fail(
                f"Instantiating with empty 'replace' raised an unexpected exception: {e}"
            )

    def test_empty_file_path_raises_error(self):
        """Tests that a whitespace-only file_path raises a ValueError."""
        with pytest.raises(ValueError, match="'file_path' parameter cannot be empty"):
            EditAction(file_path=" ", find="old", replace="new")

    @pytest.mark.parametrize("param", ["file_path", "find", "replace"])
    def test_non_string_params_raise_error(self, param):
        """Tests that non-string parameters raise a TypeError."""
        with pytest.raises(TypeError, match=f"'{param}' must be a string"):
            params = {"file_path": "path/to/file.txt", "find": "old", "replace": "new"}
            params[param] = 123
            EditAction(**params)


class TestChatWithUserAction:
    def test_instantiation_happy_path(self):
        """Tests happy path instantiation for ChatWithUserAction."""
        action = ChatWithUserAction(prompt="What is your name?")
        assert action.prompt == "What is your name?"
        assert action.action_type == "chat_with_user"

    def test_empty_prompt_raises_error(self):
        """Tests that an empty prompt raises a ValueError."""
        with pytest.raises(ValueError, match="'prompt' parameter cannot be empty"):
            ChatWithUserAction(prompt=" ")

    def test_non_string_prompt_raises_error(self):
        """Tests that a non-string prompt raises a TypeError."""
        with pytest.raises(TypeError, match="'prompt' must be a string"):
            ChatWithUserAction(prompt=123)
