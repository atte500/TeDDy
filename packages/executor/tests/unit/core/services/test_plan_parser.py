from pathlib import Path

from teddy_executor.core.domain.models import V2_Plan
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.services.plan_parser import PlanParser


class FakeFileSystemManager(FileSystemManager):
    """A test double for the FileSystemManager that returns predefined content."""

    def __init__(self, content: str = ""):
        self._content = content

    # --- Interface Methods ---

    def read_file(self, path: str) -> str:
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
