import json
from typing import List

from teddy.core.domain.models import ContextResult, FileContext
from teddy.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy.core.ports.outbound.file_system_manager import FileSystemManager
from teddy.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy.core.ports.outbound.environment_inspector import IEnvironmentInspector


class ContextService(IGetContextUseCase):
    """
    Application service for orchestrating the gathering of project context.
    """

    def __init__(
        self,
        file_system_manager: FileSystemManager,
        repo_tree_generator: IRepoTreeGenerator,
        environment_inspector: IEnvironmentInspector,
    ):
        self.file_system_manager = file_system_manager
        self.repo_tree_generator = repo_tree_generator
        self.environment_inspector = environment_inspector

    def _ensure_teddy_directory_exists(self):
        """Checks for and creates the .teddy directory and default files if needed."""
        if not self.file_system_manager.path_exists(".teddy"):
            self.file_system_manager.create_directory(".teddy")
            self.file_system_manager.write_file(".teddy/.gitignore", "*")
            self.file_system_manager.write_file(".teddy/context.json", "[]")
            permanent_context_content = (
                "README.md\n" "docs/ARCHITECTURE.md\n" "repotree.txt\n"
            )
            self.file_system_manager.write_file(
                ".teddy/permanent_context.txt", permanent_context_content
            )

    def _read_json_context_paths(self) -> List[str]:
        """Reads and parses .teddy/context.json, returning a list of paths."""
        try:
            content = self.file_system_manager.read_file(".teddy/context.json")
            data = json.loads(content)
            if isinstance(data, list):
                return [str(p) for p in data if p and isinstance(p, str)]
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # If file doesn't exist or is invalid, treat as empty list
        return []

    def _read_permanent_context_paths(self) -> List[str]:
        """Reads and parses .teddy/permanent_context.txt, returning a list of paths."""
        try:
            content = self.file_system_manager.read_file(".teddy/permanent_context.txt")
            return [line.strip() for line in content.splitlines() if line.strip()]
        except FileNotFoundError:
            pass  # If file doesn't exist, treat as empty list
        return []

    def _get_file_contexts(self) -> List[FileContext]:
        """Gathers file paths from all context sources and fetches their content."""
        json_paths = self._read_json_context_paths()
        permanent_paths = self._read_permanent_context_paths()

        # Combine, de-duplicate, and sort paths for deterministic order
        all_paths = sorted(list(set(json_paths + permanent_paths)))

        file_contexts = []
        for path in all_paths:
            try:
                content = self.file_system_manager.read_file(path)
                file_contexts.append(
                    FileContext(file_path=path, content=content, status="found")
                )
            except FileNotFoundError:
                file_contexts.append(
                    FileContext(file_path=path, content=None, status="not_found")
                )
        return file_contexts

    def get_context(self) -> ContextResult:
        """
        Gathers all project context information by orchestrating its dependencies.
        """
        self._ensure_teddy_directory_exists()

        repo_tree = self.repo_tree_generator.generate_tree()
        env_info = self.environment_inspector.get_environment_info()

        try:
            gitignore_content = self.file_system_manager.read_file(".gitignore")
        except FileNotFoundError:
            gitignore_content = ""

        file_contexts = self._get_file_contexts()

        return ContextResult(
            repo_tree=repo_tree,
            environment_info=env_info,
            gitignore_content=gitignore_content,
            file_contexts=file_contexts,
        )
