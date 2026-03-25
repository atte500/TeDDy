from typing import Dict, List, Optional, Sequence
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.utils.markdown import get_fence_for_content, get_language_from_path
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
        git_status = self._environment_inspector.get_git_status()
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
        content = self._format_content(
            repo_tree, scoped_paths, file_contents, git_status
        )

        # Assemble and return the DTO
        return ProjectContext(
            header=header,
            content=content,
            scoped_paths=scoped_paths,
            git_status=git_status,
        )

    def _format_header(self, system_info: Dict[str, str]) -> str:
        """Formats the header section of the context report."""
        header_parts = [
            "# Project Context",
            "\n## 1. System Information",
            f"- **CWD:** {system_info.get('cwd', 'N/A')}",
            f"- **OS:** {system_info.get('os_name', 'N/A')} {system_info.get('os_version', 'N/A')}".strip(),
            f"- **Shell:** {system_info.get('shell', 'N/A')}",
        ]
        return "\n".join(header_parts)

    def _format_content(
        self,
        repo_tree: str,
        scoped_paths: Dict[str, List[str]],
        file_contents: Dict[str, Optional[str]],
        git_status: Optional[str] = None,
    ) -> str:
        """Formats the main content section of the context report."""
        content_parts = [
            "\n## 2. Git Status",
            git_status if git_status is not None else "",
            "\n## 3. Project Structure",
            f"```\n{repo_tree}\n```",
        ]

        content_parts.extend(
            self._format_resource_contents(scoped_paths, file_contents)
        )

        return "\n".join(content_parts)

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

        parts = ["\n## 4. Resource Contents"]
        for path in unique_paths:
            parts.append("\n---")
            parts.append(f"### [{path}](/{path})")
            content = file_contents.get(path)
            if content is not None:
                lang = get_language_from_path(path)
                fence = get_fence_for_content(content)
                parts.append(f"{fence}{lang}\n{content}\n{fence}")
            else:
                parts.append("```\n--- FILE NOT FOUND ---\n```")
        return parts
