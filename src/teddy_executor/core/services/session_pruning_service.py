import re
from dataclasses import is_dataclass, replace
from typing import Any, Dict, Optional

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


class SessionPruningService:
    """
    Encapsulates auto-pruning heuristics for session context.
    """

    def __init__(
        self,
        config_service: IConfigService,
        file_system_manager: IFileSystemManager,
    ):
        self._config_service = config_service
        self._file_system_manager = file_system_manager
        self._read_cache: Dict[str, str] = {}

    def prune(
        self, context: ProjectContext, current_status: Optional[str] = None
    ) -> ProjectContext:
        """Applies configured auto-pruning heuristics to the project context."""
        self._read_cache.clear()
        try:
            if not self._config_service.get_setting("auto_pruning.enabled", True):
                return context

            # Handle MagicMocks in unit tests
            if not is_dataclass(context):
                return context

            items = list(context.items)

            # 1. Prune by status/validation failure (Heuristics 3 & 4)
            # Returns turns_to_prune mapping and a set of turns that MUST be spared
            turns_to_prune, spared_turns = self._identify_turns_to_prune(
                items, current_status
            )

            for i, item in enumerate(items):
                new_item = self._process_context_item(item, turns_to_prune)
                if new_item is not item:
                    items[i] = new_item

            # 2. Heuristic 6: Retention Limit
            items = self._apply_retention_limit(items, spared_turns=spared_turns)

            # 3. Heuristic 2: Global Budget
            system_prompt_tokens = context.system_prompt_tokens or 0
            items = self._apply_global_budget(
                items, system_prompt_tokens=system_prompt_tokens
            )

            return replace(context, items=items)
        except Exception as e:
            # Failure Transparency: Log and re-raise or return original context
            import sys

            print(f"[ERROR] PruningService failure: {e}", file=sys.stderr)
            return context

    def _process_context_item(self, item: Any, turns_to_prune: Dict[str, str]) -> Any:
        """Processes an individual context item for pruning."""
        if item.scope != "Turn":
            return item

        if item.git_status == "D":
            return replace(
                item, selected=False, auto_prune_reason="File deleted from disk"
            )

        # Normalize path for consistent string matching
        posix_path = item.path.replace("\\", "/").lstrip("./").lstrip("/")

        # Match numeric turn directories (e.g. '01', '02')
        turn_id = self._extract_turn_id(posix_path)
        if turn_id:
            # Check both raw string and integer-normalized version
            reason = turns_to_prune.get(turn_id) or turns_to_prune.get(
                str(int(turn_id))
            )
            if reason:
                return replace(
                    item,
                    selected=False,
                    auto_prune_reason=reason,
                )

        return item

    def _extract_turn_id(self, path: str) -> Optional[str]:
        """Extracts the last numeric directory segment from the path."""
        if not isinstance(path, str):
            return None
        # Normalize to forward slashes and strip prefixes for consistent matching
        normalized = path.replace("\\", "/").lstrip("./").lstrip("/")
        # Turn IDs are typically 1-3 digits. 4+ digits usually represent years or other data.
        matches = re.findall(r"(?:^|/)(\d{1,3})(?=/|$)", normalized)
        return matches[-1] if matches else None

    def _identify_turns_to_prune(
        self, items, current_status: Optional[str] = None
    ) -> tuple[Dict[str, str], set[int]]:
        """Identifies turns that should be pruned based on failure status."""
        prune_non_green = bool(
            self._config_service.get_setting("auto_pruning.prune_failure_history", True)
        )
        prune_validation = bool(
            self._config_service.get_setting(
                "auto_pruning.prune_validation_failures", True
            )
        )
        preserve_messages = bool(
            self._config_service.get_setting(
                "auto_pruning.preserve_message_turns", True
            )
        )

        turn_statuses, validation_failures, successful_messages = (
            self._collect_turn_metadata(
                items, prune_non_green, prune_validation, preserve_messages
            )
        )

        turns_to_prune = self._apply_pruning_heuristics(
            turn_statuses, validation_failures, prune_non_green, current_status
        )

        # Explicitly remove preserved message turns from the prune list
        if preserve_messages:
            for tid in successful_messages:
                turns_to_prune.pop(str(tid), None)

        return turns_to_prune, successful_messages if preserve_messages else set()

    def _collect_turn_metadata(
        self,
        items,
        prune_non_green: bool,
        prune_validation: bool,
        preserve_messages: bool = False,
    ) -> tuple[Dict[int, bool], set[int], set[int]]:
        """Scans items to determine turn statuses and validation failures."""
        turn_statuses: Dict[int, bool] = {}
        validation_failures: set[int] = set()
        successful_messages: set[int] = set()
        checked_paths = set()

        for item in items:
            if item.scope != "Turn" or item.path in checked_paths:
                continue

            posix_path = item.path.replace("\\", "/")
            turn_id_str = self._extract_turn_id(posix_path)
            if not turn_id_str:
                continue

            turn_id = int(turn_id_str)
            checked_paths.add(item.path)

            self._update_turn_metadata_from_item(
                item,
                posix_path,
                turn_id,
                {
                    "statuses": turn_statuses,
                    "validation_fails": validation_failures,
                    "messages": successful_messages,
                },
                {
                    "non_green": prune_non_green,
                    "validation": prune_validation,
                    "messages": preserve_messages,
                },
            )

        return turn_statuses, validation_failures, successful_messages

    def _update_turn_metadata_from_item(
        self,
        item: Any,
        posix_path: str,
        turn_id: int,
        state: Dict[str, Any],
        config: Dict[str, bool],
    ) -> None:
        """Processes a single item to update turn-level metadata."""
        # --- 1. Identify Metadata for Pruning ---

        # Heuristic 4: Validation failure (Check report)
        if config["validation"] and posix_path.endswith("report.md"):
            if self._check_report_failed_validation(item.path):
                state["validation_fails"].add(turn_id)

        # Heuristic 3: Non-green state (Check plan)
        if posix_path.endswith("plan.md"):
            is_failed = self._check_plan_failed(item.path)
            if config["non_green"]:
                is_green = not is_failed
                # If any file in turn is non-green, the whole turn is non-green
                state["statuses"][turn_id] = (
                    state["statuses"].get(turn_id, True) and is_green
                )

        # --- 2. Identify Metadata for Sparing ---

        # Sparing Rule: Successful Message Turns
        if config["messages"] and posix_path.endswith("plan.md"):
            if self._check_plan_is_message(item.path):
                # We only spare if the turn resulted in a SUCCESSFUL execution.
                # We ignore the plan's internal status (is_failed)
                # and the report's validation status (is_validation_fail) here,
                # as a successful message is valuable regardless.
                report_path = item.path.replace("plan.md", "report.md")
                if self._check_report_is_success(report_path):
                    state["messages"].add(turn_id)

    def _check_plan_is_message(self, path: str) -> bool:
        """Checks if a plan file contains a ## Message section."""
        content = self._safe_read(path)
        if content:
            return bool(re.search(r"^## Message", content, re.MULTILINE))
        return False

    def _check_plan_failed(self, path: str) -> bool:
        """Checks if a plan file contains a failure status emoji on the status line."""
        content = self._safe_read(path)
        if content:
            # Anchored to start of line to avoid matches in rationales or code blocks
            return bool(re.search(r"^- \*\*Status:\*\*.*[🔴🟡]", content, re.MULTILINE))
        return False

    def _check_report_failed_validation(self, path: str) -> bool:
        """Checks if a report file contains the official validation failure status."""
        content = self._safe_read(path)
        if content:
            # Anchored to target the standardized overall status line
            return bool(
                re.search(
                    r"^- \*\*Overall Status:\*\* Validation Failed",
                    content,
                    re.MULTILINE,
                )
            )
        return False

    def _check_report_is_success(self, path: str) -> bool:
        """Checks if a report file contains the official success status."""
        content = self._safe_read(path)
        if content:
            # Anchored to target the standardized overall status line
            return bool(
                re.search(
                    r"^- \*\*Overall Status:\*\* SUCCESS",
                    content,
                    re.MULTILINE,
                )
            )
        return False

    def _safe_read(self, path: str) -> Optional[str]:
        """Reads a file with caching and error handling."""
        if path in self._read_cache:
            return self._read_cache[path]
        try:
            if self._file_system_manager.path_exists(path):
                content = self._file_system_manager.read_file(path)
                self._read_cache[path] = content
                return content
        except (FileNotFoundError, OSError):
            pass
        return None

    def _check_file_contains(self, path: str, patterns: str | tuple[str, ...]) -> bool:
        """Safely checks if a file exists and contains specific patterns."""
        try:
            if self._file_system_manager.path_exists(path):
                content = self._file_system_manager.read_file(path)
                if isinstance(patterns, str):
                    return patterns in content
                return any(p in content for p in patterns)
        except (FileNotFoundError, OSError):
            pass
        return False

    def _apply_pruning_heuristics(
        self,
        turn_statuses: Dict[int, bool],
        validation_failures: set[int],
        prune_non_green: bool,
        current_status: Optional[str] = None,
    ) -> Dict[str, str]:
        """Applies heuristics to the collected metadata."""
        turns_to_prune: Dict[str, str] = {}

        # Heuristic 4: Validation Failure
        for tid in validation_failures:
            turns_to_prune[str(tid)] = "Plan failed validation"

        # Heuristic 3: Recovery Cleanup
        # If current_status is Green, OR if the latest turn on disk is Green, prune failures.
        is_currently_green = current_status is not None and "🟢" in current_status

        if prune_non_green and turn_statuses:
            latest_on_disk = max(turn_statuses.keys())
            is_latest_green = turn_statuses[latest_on_disk]

            if is_currently_green or is_latest_green:
                for tid, is_green in turn_statuses.items():
                    if not is_green:
                        turns_to_prune.setdefault(
                            str(tid), "Pruned failure history after successful recovery"
                        )

        return turns_to_prune

    def _apply_retention_limit(self, items, spared_turns: Optional[set[int]] = None):
        """Prunes turn context items that exceed the turn retention limit."""
        try:
            setting = self._config_service.get_setting(
                "auto_pruning.max_turns_retention", 0
            )
            limit = int(setting) if setting is not None else 0
        except (TypeError, ValueError):
            limit = 0

        if limit <= 0:
            return items

        turn_id_map, max_id = self._map_turn_ids(items)
        if max_id == -1:
            return items

        # Calculate threshold and prune
        threshold = max_id - limit
        reason = f"Turn exceeds retention limit of {limit}"
        spared = spared_turns or set()

        for idx, tid in turn_id_map.items():
            if tid <= threshold and tid not in spared:
                items[idx] = replace(
                    items[idx],
                    selected=False,
                    auto_prune_reason=reason,
                )

        return items

    def _map_turn_ids(self, items) -> tuple[Dict[int, int], int]:
        """Identifies turn IDs and the maximum ID in the context items."""
        max_id = -1
        turn_id_map = {}  # idx -> int_id

        for i, item in enumerate(items):
            if item.scope != "Turn":
                continue

            tid_str = self._extract_turn_id(item.path)
            if tid_str:
                try:
                    tid = int(tid_str)
                    turn_id_map[i] = tid
                    max_id = max(max_id, tid)
                except (ValueError, TypeError):
                    continue
        return turn_id_map, max_id

    def _apply_global_budget(self, items, system_prompt_tokens: int = 0):
        """Prunes turn and history context items to fit within a global token budget."""
        try:
            setting = self._config_service.get_setting(
                "auto_pruning.global_context_threshold", 0
            )
            threshold = int(setting) if setting is not None else 0
        except (TypeError, ValueError):
            threshold = 0

        if threshold > 0:
            # Sum ALL selected items plus system prompt tokens to reflect true context size
            total_tokens = system_prompt_tokens + sum(
                item.token_count
                for item in items
                if item.selected and isinstance(item.token_count, (int, float))
            )

            if total_tokens > threshold:
                # Gather eligible pruning candidates: standard Turn files (which includes history files in turn.context)
                prune_candidates = [
                    (i, item)
                    for i, item in enumerate(items)
                    if item.scope == "Turn"
                    and item.selected
                    and isinstance(item.token_count, (int, float))
                ]

                # Sort by token count descending to prune largest files first
                prune_candidates.sort(key=lambda x: x[1].token_count, reverse=True)

                for idx, item in prune_candidates:
                    if total_tokens <= threshold:
                        break
                    items[idx] = replace(
                        item,
                        selected=False,
                        auto_prune_reason="Pruned to fit context budget",
                    )
                    total_tokens -= item.token_count
        return items
