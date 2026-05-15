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
        """Applies configured auto-pruning heuristics to the project context."""
        try:
            if not self._config_service.get_setting("auto_pruning.enabled", True):
                return context

            # Handle MagicMocks in unit tests
            if not is_dataclass(context):
                return context

            items = list(context.items)

            # 1. Prune by status/validation failure (Heuristics 3 & 4)
            turns_to_prune = self._identify_turns_to_prune(items, current_status)

            for i, item in enumerate(items):
                new_item = self._process_context_item(item, turns_to_prune)
                if new_item is not item:
                    items[i] = new_item

            # 2. Heuristic 6: Retention Limit
            items = self._apply_retention_limit(items)

            # 3. Heuristic 2: Global Budget
            items = self._apply_global_budget(items)

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
        # Normalize to forward slashes and strip prefixes for consistent matching
        normalized = path.replace("\\", "/").lstrip("./").lstrip("/")
        # Turn IDs are typically 1-3 digits. 4+ digits usually represent years or other data.
        matches = re.findall(r"(?:^|/)(\d{1,3})(?=/|$)", normalized)
        return matches[-1] if matches else None

    def _identify_turns_to_prune(
        self, items, current_status: Optional[str] = None
    ) -> Dict[str, str]:
        """Identifies turns that should be pruned based on failure status."""
        prune_non_green = bool(
            self._config_service.get_setting("auto_pruning.prune_failure_history", True)
        )
        prune_validation = bool(
            self._config_service.get_setting(
                "auto_pruning.prune_validation_failures", True
            )
        )

        turn_statuses, validation_failures = self._collect_turn_metadata(
            items, prune_non_green, prune_validation
        )

        return self._apply_pruning_heuristics(
            turn_statuses, validation_failures, prune_non_green, current_status
        )

    def _collect_turn_metadata(
        self, items, prune_non_green: bool, prune_validation: bool
    ) -> tuple[Dict[int, bool], set[int]]:
        """Scans items to determine turn statuses and validation failures."""
        turn_statuses: Dict[int, bool] = {}
        validation_failures: set[int] = set()
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

            # Heuristic 4: Validation failure (Check report)
            if prune_validation and posix_path.endswith("report.md"):
                if self._check_report_failed_validation(item.path):
                    validation_failures.add(turn_id)

            # Heuristic 3: Non-green state (Check plan)
            if prune_non_green and posix_path.endswith("plan.md"):
                is_green = not self._check_plan_failed(item.path)
                # If any file in turn is non-green, the whole turn is non-green
                turn_statuses[turn_id] = turn_statuses.get(turn_id, True) and is_green

        return turn_statuses, validation_failures

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

    def _apply_retention_limit(self, items):
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

        # 1. Identify max turn_id
        max_id = -1
        turn_id_map = {}  # idx -> int_id

        for i, item in enumerate(items):
            if item.scope != "Turn":
                continue

            # Use existing extractor
            tid_str = self._extract_turn_id(item.path)
            if tid_str:
                tid = int(tid_str)
                turn_id_map[i] = tid
                max_id = max(max_id, tid)

        if max_id == -1:
            return items

        # 2. Calculate threshold and prune
        threshold = max_id - limit
        reason = f"Turn exceeds retention limit of {limit}"

        for idx, tid in turn_id_map.items():
            if tid <= threshold:
                items[idx] = replace(
                    items[idx],
                    selected=False,
                    auto_prune_reason=reason,
                )

        return items

    def _apply_global_budget(self, items):
        """Prunes turn context items to fit within a global token budget."""
        try:
            setting = self._config_service.get_setting(
                "auto_pruning.global_context_threshold", 0
            )
            threshold = int(setting) if setting is not None else 0
        except (TypeError, ValueError):
            threshold = 0

        if threshold > 0:
            turn_items = [
                (i, item)
                for i, item in enumerate(items)
                if item.scope == "Turn"
                and item.selected
                and isinstance(item.token_count, (int, float))
            ]
            total_tokens = sum(item.token_count for _, item in turn_items)

            if total_tokens > threshold:
                # Sort by token count descending
                turn_items.sort(key=lambda x: x[1].token_count, reverse=True)
                for idx, item in turn_items:
                    if total_tokens <= threshold:
                        break
                    items[idx] = replace(
                        item,
                        selected=False,
                        auto_prune_reason="Pruned to fit context budget",
                    )
                    total_tokens -= item.token_count
        return items
