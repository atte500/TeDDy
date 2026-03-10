from typing import Dict, List, Optional, Sequence
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
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
        file_system_manager: IFileSystemManager,
        repo_tree_generator: IRepoTreeGenerator,
        environment_inspector: IEnvironmentInspector,
    ):
        self._file_system_manager = file_system_manager
        self._repo_tree_generator = repo_tree_generator
        self._environment_inspector = environment_inspector

    def get_context(
        self, context_files: Optional[Dict[str, Sequence[str]]] = None
    ) -> ProjectContext:
        """
        Gathers all project context information by orchestrating its dependencies.
        """
        # Gather all information from outbound ports
        system_info = self._environment_inspector.get_environment_info()
        repo_tree = self._repo_tree_generator.generate_tree()

        scoped_paths: Dict[str, List[str]] = {}
        all_resolved_paths: List[str] = []

        if context_files:
            # Backward compatibility: handle list of files by wrapping in 'Default' scope
            if isinstance(context_files, list):
                context_files = {"Default": context_files}

            for scope, files in context_files.items():
                paths = self._file_system_manager.resolve_paths_from_files(files)
                scoped_paths[scope] = paths
                for p in paths:
                    if p not in all_resolved_paths:
                        all_resolved_paths.append(p)
        else:
            all_resolved_paths = self._file_system_manager.get_context_paths()
            scoped_paths["Default"] = all_resolved_paths

        file_contents = self._file_system_manager.read_files_in_vault(
            all_resolved_paths
        )

        header = self._format_header(system_info)
        content = self._format_content(repo_tree, scoped_paths, file_contents)

        # Assemble and return the DTO
        return ProjectContext(header=header, content=content, scoped_paths=scoped_paths)

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
        scoped_paths: Dict[str, List[str]],
        file_contents: Dict[str, Optional[str]],
    ) -> str:
        """Formats the main content section of the context report."""
        content_parts = ["\n# Repository Tree", repo_tree]

        content_parts.extend(self._format_context_summary(scoped_paths))
        content_parts.extend(
            self._format_resource_contents(scoped_paths, file_contents)
        )

        return "\n".join(content_parts)

    def _format_context_summary(self, scoped_paths: Dict[str, List[str]]) -> List[str]:
        """Formats the Context Summary section."""
        if not scoped_paths:
            return []

        parts = ["\n# Context Summary"]
        for scope, paths in scoped_paths.items():
            if paths:
                parts.append(f"### {scope}")
                for path in paths:
                    parts.append(f"- [{path}](/{path})")
        return parts

    def _format_resource_contents(
        self,
        scoped_paths: Dict[str, List[str]],
        file_contents: Dict[str, Optional[str]],
    ) -> List[str]:
        """Formats the Resource Contents section."""
        unique_paths: List[str] = []
        for paths in scoped_paths.values():
            for p in paths:
                if p not in unique_paths:
                    unique_paths.append(p)

        if not unique_paths:
            return []

        parts = ["\n# Resource Contents"]
        for path in unique_paths:
            parts.append(f"## [{path}](/{path})")
            content = file_contents.get(path)
            if content is not None:
                lang = path.split(".")[-1] if "." in path else ""
                parts.append(f"```{lang}\n{content}\n```")
            else:
                parts.append("```\n--- FILE NOT FOUND ---\n```")
        return parts
