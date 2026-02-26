from typing import Dict, List, Optional
from teddy_executor.core.domain.models import ProjectContext
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
        self._file_system_manager = file_system_manager
        self._repo_tree_generator = repo_tree_generator
        self._environment_inspector = environment_inspector

    def get_context(self) -> ProjectContext:
        """
        Gathers all project context information by orchestrating its dependencies.
        """
        # Scenario 2: Simplified Default Configuration
        if not self._file_system_manager.path_exists(".teddy/project.context"):
            self._file_system_manager.create_default_context_file()

        # Gather all information from outbound ports
        system_info = self._environment_inspector.get_environment_info()
        repo_tree = self._repo_tree_generator.generate_tree()
        context_vault_paths = self._file_system_manager.get_context_paths()
        file_contents = self._file_system_manager.read_files_in_vault(
            context_vault_paths
        )

        header = self._format_header(system_info)
        content = self._format_content(repo_tree, context_vault_paths, file_contents)

        # Assemble and return the DTO
        return ProjectContext(header=header, content=content)

    def _format_header(self, system_info: Dict[str, str]) -> str:
        """Formats the header section of the context report."""
        header_parts = [
            "# System Information",
            f"cwd: {system_info.get('cwd', 'N/A')}",
            f"os_name: {system_info.get('os_name', 'N/A')}",
            f"os_version: {system_info.get('os_version', 'N/A')}",
            f"shell: {system_info.get('shell', 'N/A')}",
        ]
        return "\n".join(header_parts)

    def _format_content(
        self,
        repo_tree: str,
        context_vault_paths: List[str],
        file_contents: Dict[str, Optional[str]],
    ) -> str:
        """Formats the main content section of the context report."""
        content_parts = ["\n# Repository Tree", repo_tree]
        if context_vault_paths:
            content_parts.append("\n# Context Vault")
            for path in context_vault_paths:
                content_parts.append(f"## [{path}](/{path})")
                content = file_contents.get(path)
                if content is not None:
                    lang = path.split(".")[-1] if "." in path else ""
                    content_parts.append(f"```{lang}\n{content}\n```")
                else:
                    content_parts.append("```\n--- FILE NOT FOUND ---\n```")
        return "\n".join(content_parts)
