from pathlib import Path

import pytest

from teddy_executor.core.domain.models import V2_Plan
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.services.plan_parser import PlanParser, PlanNotFoundError


class FakeFileSystemManager(FileSystemManager):
    """A test double for the FileSystemManager that returns predefined content."""

    def __init__(self, content: str = "", file_exists: bool = True):
        self._content = content
        self._file_exists = file_exists

    # --- Interface Methods ---

    def read_file(self, path: str) -> str:
        if not self._file_exists:
            raise FileNotFoundError(f"File not found: {path}")
        return self._content

    # --- Stubs for unused methods ---

    def path_exists(self, path: str) -> bool:
        raise NotImplementedError

    def create_directory(self, path: str) -> None:
        raise NotImplementedError

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError

    def create_file(self, path: str, content: str) -> None:
        raise NotImplementedError

    def edit_file(self, path: str, find: str, replace: str) -> None:
        raise NotImplementedError

    def create_default_context_file(self) -> None:
        raise NotImplementedError

    def get_context_paths(self) -> list[str]:
        raise NotImplementedError

    def read_files_in_vault(self, paths: list[str]) -> dict[str, str | None]:
        raise NotImplementedError


def test_parse_success_scenario():
    """
    Given a valid plan file content,
    When the plan is parsed,
    Then a valid Plan domain object is returned.
    """
    # Arrange
    plan_content = """
    actions:
      - type: create_file
        path: "hello.txt"
        content: "Hello, World!"
      - type: execute
        command: "echo 'done'"
    """
    dummy_path = Path("plan.yaml")
    fake_fs_manager = FakeFileSystemManager(content=plan_content)

    # This is the class we are testing
    plan_parser = PlanParser(file_system_manager=fake_fs_manager)

    # Act
    result_plan = plan_parser.parse(plan_path=dummy_path)

    # Assert
    assert isinstance(result_plan, V2_Plan)
    assert len(result_plan.actions) == 2

    assert result_plan.actions[0].type == "create_file"
    assert result_plan.actions[0].params == {
        "path": "hello.txt",
        "content": "Hello, World!",
    }

    assert result_plan.actions[1].type == "execute"
    assert result_plan.actions[1].params == {"command": "echo 'done'"}


def test_parse_raises_plan_not_found_when_file_does_not_exist():
    """
    Given a file system manager that reports a file does not exist,
    When the plan is parsed,
    Then a PlanNotFoundError should be raised.
    """
    # Arrange
    dummy_path = Path("non_existent_plan.yaml")
    # Configure the fake to simulate a missing file
    fake_fs_manager = FakeFileSystemManager(file_exists=False)
    plan_parser = PlanParser(file_system_manager=fake_fs_manager)

    # Act & Assert
    with pytest.raises(
        PlanNotFoundError, match=f"Plan file not found at: {dummy_path}"
    ):
        plan_parser.parse(plan_path=dummy_path)
