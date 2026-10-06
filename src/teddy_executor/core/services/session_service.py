import re
from pathlib import Path
from typing import Any, Dict, Optional
from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ExecutionReport,
)
from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.domain.models.plan import ActionType
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.utils.string import slugify


class SessionService(ISessionManager):
    """
    Service for managing session directories and metadata.
    """

    def __init__(  # noqa: PLR0913
        self,
        file_system_manager: IFileSystemManager,
        repository: ISessionRepository,
        time_service: ITimeService,
        prompt_manager: IPromptManager,
        init_service: IInitUseCase,
        config_service: IConfigService,
    ):
        self._file_system_manager = file_system_manager
        self._repository = repository
        self._time_service = time_service
        self._prompt_manager = prompt_manager
        self._init_service = init_service
        self._config_service = config_service

    def create_session(
        self,
        options: SessionOptions,
    ) -> str:
        """
        Initializes a new session directory and bootstraps it for Turn 1.
        """
        timestamp = self._time_service.now().strftime("%Y%m%d_%H%M%S")
        clean_name = slugify(options.name) or "session"
        session_root = self._claim_session_root(f"{timestamp}-{clean_name}")
        turn_dir = f"{session_root}/01"

        self._repository.create_turn_directory(turn_dir)

        # 1. Context Seeding
        clean_context = self._prepare_session_context(session_root, options)
        self._file_system_manager.write_file(
            f"{session_root}/session.context", clean_context
        )

        # 2. Prompt population — read from .teddy/prompts/ (canonical source)
        prompt_filename, prompt_content = self._resolve_agent_prompt(options.agent_name)
        self._file_system_manager.write_file(
            f"{session_root}/{prompt_filename}", prompt_content
        )

        # 3. Metadata persistence
        meta_data = self._initialize_meta_data(options)
        self._repository.save_meta(f"{turn_dir}/meta.yaml", meta_data)

        return session_root

    def _prepare_session_context(
        self, session_root: str, options: SessionOptions
    ) -> str:
        """Seeds and merges context for the new session."""
        init_context_path = ".teddy/init.context"
        if not self._file_system_manager.path_exists(init_context_path):
            self._init_service.ensure_initialized()

        if not self._file_system_manager.path_exists(init_context_path):
            raise FileNotFoundError(
                f"Initialization failed: {init_context_path} not found."
            )

        init_context = self._file_system_manager.read_file(init_context_path)
        clean_lines = [
            line.strip()
            for line in init_context.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        # Merge additional context with path normalization
        for path in options.additional_context:
            if path:
                normalized = path.strip().replace("\\", "/")
                if normalized.startswith("./"):
                    normalized = normalized[2:]
                normalized = normalized.lstrip("/")
                if normalized and normalized not in clean_lines:
                    clean_lines.append(normalized)

        # Add initial_request path BEFORE dedup so it's also deduplicated
        if options.initial_request:
            req_path = f"{session_root}/initial_request.md"
            self._file_system_manager.write_file(req_path, options.initial_request)
            rel_path = str(
                self.to_root_relative(Path(session_root), "initial_request.md")
            )
            clean_lines.append(rel_path)

        # Deduplicate preserving insertion order (dict preserves insertion order)
        deduped = list(dict.fromkeys(clean_lines))
        return "\n".join(deduped)

    def _initialize_meta_data(self, options: SessionOptions) -> Dict[str, Any]:
        """Creates the initial metadata dictionary."""
        meta_data = {
            "turn_id": "01",
            "agent_name": options.agent_name,
            "cumulative_cost": 0.0,
            "turn_cost": 0.0,
            "creation_timestamp": self._time_service.now_utc().isoformat(),
        }
        if options.model:
            meta_data["model"] = options.model
        if options.api_key:
            meta_data["api_key"] = options.api_key
        return meta_data

    def _resolve_agent_prompt(self, agent_name: str) -> tuple[str, str]:
        """
        Resolves an agent's prompt file from .teddy/prompts/ via casefold stem matching.

        Returns:
            (prompt_filename, prompt_content)

        Raises:
            ValueError: If the prompts directory is missing or no matching prompt exists.
        """
        prompts_dir = ".teddy/prompts"
        if not self._file_system_manager.path_exists(prompts_dir):
            available = self._prompt_manager.get_available_agents()
            if available:
                msg = (
                    f"Agent prompt '{agent_name}' not found in .teddy/prompts/. "
                    f"Available agents: {', '.join(available)}"
                )
            else:
                msg = (
                    f"Agent prompt '{agent_name}' not found in .teddy/prompts/. "
                    "Please run 'teddy init' to restore prompts."
                )
            raise ValueError(msg)

        prompt_filename = None
        for f in self._file_system_manager.list_directory(prompts_dir):
            if Path(f).stem.casefold() == agent_name.casefold():
                prompt_filename = f
                break

        if prompt_filename is None:
            available = self._prompt_manager.get_available_agents()
            if available:
                msg = (
                    f"Agent prompt '{agent_name}' not found in .teddy/prompts/. "
                    f"Available agents: {', '.join(available)}"
                )
            else:
                msg = (
                    f"Agent prompt '{agent_name}' not found in .teddy/prompts/. "
                    "Please run 'teddy init' to restore prompts."
                )
            raise ValueError(msg)

        prompt_path = f"{prompts_dir}/{prompt_filename}"
        prompt_content = self._file_system_manager.read_file(prompt_path)
        return prompt_filename, prompt_content

    def get_latest_turn(self, session_name: str) -> str:
        """
        Identifies and returns the latest turn directory in the specified session.
        """
        return self._repository.get_latest_turn(session_name)

    def get_session_state(self, session_name: str) -> tuple[SessionState, str]:
        """
        Determines the state of the session and returns the state and the path
        to the latest turn.
        """
        latest_turn_path = self.get_latest_turn(session_name)

        plan_exists = self._file_system_manager.path_exists(
            f"{latest_turn_path}/plan.md"
        )
        report_exists = self._file_system_manager.path_exists(
            f"{latest_turn_path}/report.md"
        )

        if report_exists:
            return SessionState.COMPLETE_TURN, latest_turn_path
        if plan_exists:
            return SessionState.PENDING_PLAN, latest_turn_path

        return SessionState.EMPTY, latest_turn_path

    def get_cumulative_cost(self, session_name: str) -> float:
        """
        Retrieves the total cumulative cost for the session from the latest turn's metadata.
        """
        latest_turn_path = self.get_latest_turn(session_name)
        if not latest_turn_path:
            return 0.0

        meta = self._repository.load_meta(latest_turn_path)
        return float(meta.get("cumulative_cost", 0.0))

    def load_turn_meta(self, turn_dir: str) -> Dict[str, Any]:
        """Loads the metadata of a turn via the injected repository."""
        return self._repository.load_meta(turn_dir)

    def save_turn_meta(self, turn_dir: str, data: Dict[str, Any]) -> None:
        """Persists the metadata of a turn via the injected repository."""
        self._repository.save_meta(f"{turn_dir}/meta.yaml", data)

    def _extract_resource_path(self, resource_str: str) -> str:
        """
        Extracts the path from a Markdown link or returns the string if not a link.
        Normalizes all slashes to forward slashes.
        Only strips the exact "./" prefix if present, preserving leading dots.
        """
        match = re.search(r"\[.*\]\((.*)\)", resource_str)
        if match:
            path = match.group(1)
            normalized = path.replace("\\", "/")
            # Only strip the exact "./" prefix if present (preserves leading dots)
            if normalized.startswith("./"):
                normalized = normalized.removeprefix("./")
            return normalized.lstrip("/")
        normalized = resource_str.strip().replace("\\", "/")
        # Only strip the exact "./" prefix if present (preserves leading dots)
        if normalized.startswith("./"):
            normalized = normalized.removeprefix("./")
        return normalized.lstrip("/")

    def transition_to_next_turn(
        self,
        plan_path: str,
        execution_report: Optional[ExecutionReport] = None,
        turn_cost: float = 0.0,
        is_validation_failure: bool = False,
        pruned_paths: Optional[list[str]] = None,
    ) -> str:
        """
        Calculates and creates the next turn directory based on the current turn
        and the outcome of its plan.
        """
        cur_dir = Path(plan_path).parent

        # 1. Resolve current state
        meta = self._repository.load_meta(cur_dir.as_posix())
        next_id, next_session_dir = self._resolve_next_turn_path(cur_dir)
        next_dir = (next_session_dir / next_id).as_posix()

        # 2. Setup next directory
        self._repository.create_turn_directory(next_dir)

        # 3. Persist metadata
        self._persist_next_meta(
            next_dir, next_id, meta, turn_cost, is_validation_failure
        )

        # 4. Handle context
        paths = self._repository.read_context_file(f"{cur_dir.as_posix()}/turn.context")

        # FIX: Apply pruning BEFORE execution effects so READ/CREATE/EDIT can re-add files.
        if pruned_paths:
            self._prune_context_paths(paths, pruned_paths, next_session_dir)

        self._apply_execution_effects(paths, execution_report)

        # Check if this turn should be preserved in session.context instead of turn.context
        preserve_messages = bool(
            self._config_service.get_setting(
                "auto_pruning.preserve_message_turns", True
            )
        )

        plan_md_path = self.to_root_relative(cur_dir, "plan.md")
        report_md_path = self.to_root_relative(cur_dir, "report.md")

        if preserve_messages and self._is_preserved_turn(cur_dir):
            # Append to session.context instead of turn.context
            self._append_to_session_context(cur_dir, {plan_md_path, report_md_path})
        else:
            # Always append BOTH plan.md and report.md to the next turn's context
            # to ensure the AI has its previous intent and the resulting outcome.
            paths.add(plan_md_path)
            paths.add(report_md_path)

        self._file_system_manager.write_file(
            f"{next_dir}/turn.context", "\n".join(sorted(list(paths)))
        )
        return next_dir

    def _prune_context_paths(
        self,
        paths: set[str],
        pruned_paths: list[str],
        next_session_dir: Path,
    ) -> None:
        """Discards pruned paths from the next turn's context set and, if present,
        from the session's persisted session.context."""
        for p in pruned_paths:
            paths.discard(p)
        # Also prune from session.context if present
        session_context_path = (next_session_dir / "session.context").as_posix()
        if self._file_system_manager.path_exists(session_context_path):
            session_paths = self._repository.read_context_file(session_context_path)
            modified = False
            for p in pruned_paths:
                if p in session_paths:
                    session_paths.discard(p)
                    modified = True
            if modified:
                self._file_system_manager.write_file(
                    session_context_path, "\n".join(sorted(list(session_paths)))
                )

    def _is_preserved_turn(self, cur_dir: Path) -> bool:
        """Checks if the current turn should be preserved in session.context.

        Returns True if the turn is a 'message turn' (plan contains ## Message)
        or a 'user-request turn' (report contains - **User Request:**).
        """
        # Check plan.md for ## Message
        plan_path = (cur_dir / "plan.md").as_posix()
        if self._file_system_manager.path_exists(plan_path):
            content = self._file_system_manager.read_file(plan_path)
            if re.search(r"^## Message", content, re.MULTILINE):
                return True

        # Check report.md for - **User Request:**
        report_path = (cur_dir / "report.md").as_posix()
        if self._file_system_manager.path_exists(report_path):
            content = self._file_system_manager.read_file(report_path)
            if re.search(r"^## User Request", content, re.MULTILINE):
                return True

        return False

    def _append_to_session_context(self, cur_dir: Path, paths: set[str]) -> None:
        """Appends paths to the session.context file."""
        session_context_path = (cur_dir.parent / "session.context").as_posix()
        existing = self._repository.read_context_file(session_context_path)
        for p in paths:
            existing.add(p)
        self._file_system_manager.write_file(
            session_context_path, "\n".join(sorted(list(existing)))
        )

    def preserve_turn_in_session_context(self, turn_dir: Path) -> None:
        """Re-evaluates a turn's preservation and admits it to session.context.

        Mirrors the preservation arm of ``transition_to_next_turn`` so a turn
        that is augmented (e.g. a ``resume -m`` user request appended to its
        report AFTER its own finalize already ran) can still be promoted into
        the prune-exempt, session-scoped ``session.context``.
        """
        preserve_messages = bool(
            self._config_service.get_setting(
                "auto_pruning.preserve_message_turns", True
            )
        )
        if not (preserve_messages and self._is_preserved_turn(Path(turn_dir))):
            return
        plan_md_path = self.to_root_relative(Path(turn_dir), "plan.md")
        report_md_path = self.to_root_relative(Path(turn_dir), "report.md")
        self._append_to_session_context(Path(turn_dir), {plan_md_path, report_md_path})

    def to_root_relative(self, turn_dir: Path, filename: str) -> str:
        """Calculates a root-relative path for a file within a turn directory."""
        return self._repository.to_root_relative(turn_dir, filename)

    def _apply_single_log_effect(self, paths: set[str], log: ActionLog) -> None:
        """Processes a single action log and adds its target path to the context set if applicable."""
        from teddy_executor.core.domain.models import ActionStatus

        # Skip only actions that were never executed (SKIPPED/PENDING).
        if log.status in (ActionStatus.SKIPPED, ActionStatus.PENDING):
            return

        # FAILURE status only contributes paths for EDIT actions (per user requirement).
        # For READ and CREATE actions, only SUCCESS status contributes.
        if (
            log.status != ActionStatus.SUCCESS
            and log.action_type != ActionType.EDIT.value
        ):
            return

        # Determine path based on action type
        resource_val = None
        if log.action_type == ActionType.READ.value:
            # Skip adding READ path to context when Lines parameter is specified (line-range read)
            if log.params.get("lines") or log.params.get("Lines"):
                return
            resource_val = log.params.get("resource") or log.params.get("Resource")
        elif log.action_type in (ActionType.CREATE.value, ActionType.EDIT.value):
            resource_val = (
                log.params.get("file_path")
                or log.params.get("File Path")
                or log.params.get("path")
            )

        if not resource_val:
            return

        path = self._extract_resource_path(resource_val)
        if self._repository.is_valid_path(path):
            paths.add(path)

    def _apply_execution_effects(
        self, paths: set[str], report: Optional[ExecutionReport]
    ) -> None:
        """Applies side effects from READ, CREATE, and EDIT actions to the context set."""
        if not report:
            return
        for log in report.action_logs:
            self._apply_single_log_effect(paths, log)

        # FIX: Also process original_actions for validation failure scenarios.
        # When action_logs is empty (validation failure), the report still contains
        # the original plan actions. Process CREATE/EDIT actions to ensure their
        # file paths are auto-added to the context.
        self._apply_original_actions_effects(paths, report)

    def _apply_original_actions_effects(
        self, paths: set[str], report: Optional[ExecutionReport]
    ) -> None:
        """
        Processes original_actions from a validation failure report as a fallback
        when action_logs is empty.
        """
        if not report or not report.original_actions:
            return
        if report.action_logs:
            return  # Only fall back when action_logs is empty

        for action in report.original_actions:
            if action.type not in (ActionType.CREATE.value, ActionType.EDIT.value):
                continue
            resource_val = (
                action.params.get("file_path")
                or action.params.get("File Path")
                or action.params.get("path")
            )
            if not resource_val:
                continue
            path = self._extract_resource_path(resource_val)
            if self._repository.is_valid_path(path):
                paths.add(path)

    def _persist_next_meta(
        self,
        next_dir: str,
        next_id: str,
        current_meta: Dict[str, Any],
        turn_cost: float,
        is_validation_failure: bool = False,
    ) -> None:
        """Calculates and persists metadata for the next turn."""
        prev_cost = current_meta.get("cumulative_cost", 0.0)
        try:
            cumulative = float(prev_cost) + float(turn_cost)
        except (TypeError, ValueError):
            cumulative = 0.0

        meta = {
            "turn_id": next_id,
            "agent_name": current_meta.get("agent_name", "pf"),
            "cumulative_cost": cumulative,
            "parent_turn_id": current_meta.get("turn_id", "00"),
            "creation_timestamp": self._time_service.now_utc().isoformat(),
        }

        # Carry over LLM overrides and actual_model for display continuity
        for key in ["model", "actual_model", "provider", "api_key"]:
            if key in current_meta:
                meta[key] = current_meta[key]

        if is_validation_failure:
            meta["is_replan"] = True
            if "user_request" in current_meta:
                meta["user_request"] = current_meta["user_request"]
        self._repository.save_meta(f"{next_dir}/meta.yaml", meta)

    def rename_session(self, old_name: str, new_name: str) -> str:
        """
        Safely renames a session directory on the filesystem.
        """
        return self._repository.rename_session(old_name, new_name)

    def resolve_context_paths(self, plan_path: str) -> dict[str, list[str]]:
        """
        Locates session.context and turn.context relative to plan_path
        and returns their contents.
        """
        return self._repository.resolve_context_paths(plan_path)

    def get_latest_session_name(self) -> str:
        """Identifies and returns the name of the latest session."""
        return self._repository.get_latest_session_name()

    def resolve_session_from_path(self, path: str) -> str:
        """Resolves a session name from a given path."""
        return self._repository.resolve_session_from_path(path)

    def resolve_session_from_slug(self, slug: str) -> str:
        """Resolves a session name from its timestamp-stripped slug."""
        return self._repository.resolve_session_from_slug(slug)

    def set_session_agent(self, session_name: str, agent_name: str) -> None:
        """
        Permanently changes the session's agent. Updates meta.yaml
        with the new agent_name and replaces the session's prompt
        XML with the new agent's prompt from .teddy/prompts/.
        """
        session_root = f".teddy/sessions/{session_name}"
        latest_turn_path = self.get_latest_turn(session_name)

        # 1. Update meta.yaml
        meta = self.load_turn_meta(latest_turn_path)
        meta["agent_name"] = agent_name
        self.save_turn_meta(latest_turn_path, meta)

        # 2. Find new prompt in .teddy/prompts/ (mirrors create_session pattern)
        prompt_filename, prompt_content = self._resolve_agent_prompt(agent_name)

        # 3. Write prompt to session root (overwrite any existing file with same stem)
        self._file_system_manager.write_file(
            f"{session_root}/{prompt_filename}", prompt_content
        )

        # 4. Remove stale prompt files (any file in session root whose stem matches a
        #    known prompt from .teddy/prompts/ but whose stem does not match the new agent)
        known_prompt_stems = {
            Path(f).stem.casefold()
            for f in self._file_system_manager.list_directory(".teddy/prompts")
        }
        new_agent_stem = agent_name.casefold()
        for f in self._file_system_manager.list_directory(session_root):
            stem = Path(f).stem.casefold()
            if stem in known_prompt_stems and stem != new_agent_stem:
                self._file_system_manager.remove_file(f"{session_root}/{f}")

    def _resolve_next_turn_path(self, cur_dir: Path) -> tuple[str, Path]:
        """Determines the next turn ID and session directory (same session)."""
        next_id = f"{int(cur_dir.name) + 1:02d}"
        return next_id, cur_dir.parent

    def _calculate_continuation_name(self, current_name: str) -> str:
        """Determines the next session name with an incremented suffix."""
        suffix_match = re.search(r"-(\d+)$", current_name)
        if suffix_match:
            count = int(suffix_match.group(1))
            base = current_name[: suffix_match.start()]
            return f"{base}-{count + 1}"
        return f"{current_name}-2"

    def _claim_session_root(self, base_name: str) -> str:
        """
        Atomically claims an unoccupied session root via exclusive creation.

        Attempts the base name first; retries follow the continuation-name
        convention via _calculate_continuation_name (an occupied {name}-N
        candidate retries {name}-N+1; suffix-free bases yield -2, -3, ...).
        Each claim is a single atomic OS operation, so exactly one process can
        win any race for a given candidate.

        Returns:
            The claimed root path (".teddy/sessions/{candidate}") for the
            first candidate whose exclusive creation succeeded.
        """
        candidate = base_name
        while True:
            root = f".teddy/sessions/{candidate}"
            if self._file_system_manager.create_directory_exclusive(root):
                return root
            candidate = self._calculate_continuation_name(candidate)
