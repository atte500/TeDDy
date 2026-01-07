from typing import List

from teddy_executor.core.domain.models import ContextResult, FileContext
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)


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
            self.file_system_manager.write_file(".teddy/context.txt", "")
            permanent_context_content = (
                ".gitignore\n"
                ".teddy/context.txt\n"
                ".teddy/permanent_context.txt\n"
                ".teddy/repotree.txt\n"
                "README.md\n"
                "docs/ARCHITECTURE.md\n"
            )
            self.file_system_manager.write_file(
                ".teddy/permanent_context.txt", permanent_context_content
            )

    def _read_context_paths(self) -> List[str]:
        """Reads and parses .teddy/context.txt, returning a list of paths."""
        try:
            content = self.file_system_manager.read_file(".teddy/context.txt")
            return [line.strip() for line in content.splitlines() if line.strip()]
        except FileNotFoundError:
            pass  # If file doesn't exist, treat as empty list
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
        context_paths = self._read_context_paths()
        permanent_paths = self._read_permanent_context_paths()

        # Combine, de-duplicate, and sort paths for deterministic order
        all_paths = sorted(list(set(context_paths + permanent_paths)))

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

        # Generate and save the repo tree first, so it's available if requested
        repo_tree = self.repo_tree_generator.generate_tree()
        self.file_system_manager.write_file(".teddy/repotree.txt", repo_tree)

        env_info = self.environment_inspector.get_environment_info()

        # This is now handled by _get_file_contexts if .gitignore is in a context file
        # For the domain object, we can pass an empty string.
        gitignore_content = ""

        file_contexts = self._get_file_contexts()

        return ContextResult(
            repo_tree="",  # No longer a special field
            environment_info=env_info,
            gitignore_content=gitignore_content,  # No longer a special field
            file_contexts=file_contexts,
        )
