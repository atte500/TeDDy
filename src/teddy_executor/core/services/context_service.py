import concurrent.futures
from typing import Dict, List, Optional, Sequence
from teddy_executor.core.domain.models import ProjectContext, ContextItem
from teddy_executor.core.utils.markdown import (
    get_fence_for_content,
    get_language_from_path,
)
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from teddy_executor.core.ports.outbound.llm_client import ILlmClient


class ContextService(IGetContextUseCase):
    """
    Application service for orchestrating the gathering of project context.
    """

    def __init__(
        self,
        file_system_manager: IFileSystemManager,
        repo_tree_generator: IRepoTreeGenerator,
        environment_inspector: IEnvironmentInspector,
        llm_client: ILlmClient,
    ):
        self._file_system_manager = file_system_manager
        self._repo_tree_generator = repo_tree_generator
        self._environment_inspector = environment_inspector
        self._llm_client = llm_client

    def get_context(
        self,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
        include_tokens: bool = True,
        agent_name: str = "Unknown",
        total_window: int = 0,
    ) -> ProjectContext:
        """
        Gathers all project context information by orchestrating its dependencies.
        """
        system_info = self._environment_inspector.get_environment_info()
        git_status = self._environment_inspector.get_git_status()
        repo_tree = self._repo_tree_generator.generate_tree()

        scoped_paths, all_resolved_paths = self._resolve_scoped_paths(context_files)
        file_contents = self._file_system_manager.read_files_in_vault(
            all_resolved_paths
        )

        system_prompt_tokens = 0
        if include_tokens and agent_name != "Unknown":
            # Heuristic: Find prompt content from common locations if not provided
            # This is a bit of a stretch as ContextService doesn't know about PromptManager
            # But we can try to get the prompt from the inspector if it was cached
            # Or just accept that system_prompt_tokens might be passed in.
            # R-10-12: The orchestrator should probably handle this calculation or pass the prompt.
            pass

        return ProjectContext(
            header=self._format_header(system_info),
            content=self._format_content(
                repo_tree, scoped_paths, file_contents, git_status
            ),
            scoped_paths=scoped_paths,
            git_status=git_status,
            items=self._collect_items(
                scoped_paths, file_contents, git_status, include_tokens
            ),
            agent_name=agent_name,
            total_window=total_window,
            system_prompt_tokens=system_prompt_tokens,
        )

    def _resolve_scoped_paths(
        self, context_files: Optional[Dict[str, Sequence[str]]]
    ) -> tuple[Dict[str, List[str]], List[str]]:
        """Resolves raw context files into scoped and deduplicated absolute paths."""
        if not context_files:
            all_paths = self._file_system_manager.get_context_paths()
            return {"Default": all_paths}, all_paths

        # Backward compatibility: handle list of files
        if isinstance(context_files, list):
            context_files = {"Default": context_files}

        scoped_paths: Dict[str, List[str]] = {}
        all_resolved_paths: List[str] = []

        for scope, files in context_files.items():
            paths = self._resolve_files_to_paths(files)
            scoped_paths[scope] = paths
            for p in paths:
                if p not in all_resolved_paths:
                    all_resolved_paths.append(p)

        return scoped_paths, all_resolved_paths

    def _resolve_files_to_paths(self, files: Sequence[str]) -> List[str]:
        """
        Nuanced Resolution: Distinguishes manifests (.context) from targets.
        Preserves original order while deduplicating results.
        """
        paths: List[str] = []
        for f in files:
            if self._is_manifest(f):
                # Expansion of manifests can return multiple paths
                resolved = self._file_system_manager.resolve_paths_from_files([f])
                for r in resolved:
                    if r not in paths:
                        paths.append(r)
            elif f not in paths:
                paths.append(f)
        return paths

    def _is_manifest(self, file_path: str) -> bool:
        """Determines if a file path refers to a .context manifest."""
        return (
            file_path.endswith(".context")
            or file_path.endswith("/context")
            or file_path == "context"
        )

    def _collect_items(
        self,
        scoped_paths: Dict[str, List[str]],
        file_contents: Dict[str, Optional[str]],
        git_status: Optional[str],
        include_tokens: bool,
    ) -> List[ContextItem]:
        """Orchestrates the assembly of ContextItem metadata DTOs."""
        parsed_status = self._parse_git_status(git_status)
        path_to_tokens = self._get_path_to_tokens(
            scoped_paths, file_contents, include_tokens
        )

        items: List[ContextItem] = []
        for scope, paths in scoped_paths.items():
            for path in paths:
                items.append(
                    ContextItem(
                        path=path,
                        token_count=path_to_tokens.get(path, 0),
                        git_status=parsed_status.get(path, ""),
                        scope=scope,
                    )
                )
        return items

    def _get_path_to_tokens(
        self,
        scoped_paths: Dict[str, List[str]],
        file_contents: Dict[str, Optional[str]],
        include_tokens: bool,
    ) -> Dict[str, int]:
        """Calculates token counts for all unique files in parallel."""
        if not include_tokens:
            return {}

        unique_paths = list(set().union(*scoped_paths.values()))
        if not unique_paths:
            return {}

        token_counts = {}

        def get_count(path: str) -> tuple[str, int]:
            content = file_contents.get(path) or ""
            return path, self._llm_client.get_text_token_count(content)

        # R-10-14: Parallelize to handle large repositories without stalling the UI.
        # We use a ThreadPoolExecutor as token counting is often offloaded or involves latency.
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_path = {
                executor.submit(get_count, path): path for path in unique_paths
            }
            for future in concurrent.futures.as_completed(future_to_path):
                path, count = future.result()
                token_counts[path] = count

        return token_counts

    def _parse_git_status(self, git_status: Optional[str]) -> Dict[str, str]:
        """Parses git status -s output into a map of path -> status code."""
        if not git_status:
            return {}

        # Minimum length for "XY path" format
        min_line_length = 4
        status_map = {}
        for line in git_status.splitlines():
            if len(line) >= min_line_length:
                code = line[:2].strip()
                path = line[3:].strip()

                # Guideline: Map ?? to U (Untracked)
                if code == "??":
                    code = "U"

                status_map[path] = code

        return status_map

    def _format_header(self, system_info: Dict[str, str]) -> str:
        """Formats the header section of the context report."""
        header_parts = [
            "# Project Context",
            "\n## 1. System Information",
            f"- **Current Date:** {system_info.get('current_date', 'N/A')}",
            f"- **Current Time:** {system_info.get('current_time', 'N/A')}",
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
        display_status = git_status
        if git_status == "":
            display_status = "nothing to commit, working tree clean"

        content_parts = [
            "\n## 2. Git Status",
            display_status if display_status is not None else "",
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
