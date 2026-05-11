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

    def prune(self, context: ProjectContext) -> ProjectContext:
        """Applies configured auto-pruning heuristics to the project context."""
        try:
            if not self._config_service.get_setting("auto_pruning.enabled", True):
                return context

            # Handle MagicMocks in unit tests
            if not is_dataclass(context):
                return context

            items = list(context.items)

            # 1. Prune by status/validation failure (Heuristics 3 & 4)
            turns_to_prune = self._identify_turns_to_prune(items)

            for i, item in enumerate(items):
                new_item = self._process_context_item(item, turns_to_prune)
                if new_item is not item:
                    items[i] = new_item

            # 2. Heuristic 2: Global Budget
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

        # Heuristic 2b: Individual File Threshold
        try:
            setting = self._config_service.get_setting(
                "auto_pruning.threshold_tokens", 0
            )
            file_threshold = int(setting) if setting is not None else 0
        except (TypeError, ValueError):
            file_threshold = 0

        if (
            file_threshold > 0
            and isinstance(item.token_count, (int, float))
            and item.token_count > file_threshold
        ):
            return replace(
                item,
                selected=False,
                auto_prune_reason="Pruned as it exceeds individual threshold",
            )

        # Match numeric turn directories (e.g. '01', '02')
        turn_id = self._extract_turn_id(item.path)
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
        # Turn IDs are typically 1-3 digits. 4+ digits usually represent years or other data.
        matches = re.findall(r"(?:^|/)(\d{1,3})(?=/|$)", path)
        return matches[-1] if matches else None

    def _identify_turns_to_prune(self, items) -> Dict[str, str]:
        """Identifies turns that should be pruned based on failure status."""
        turns_to_prune: Dict[str, str] = {}
        prune_non_green = bool(
            self._config_service.get_setting(
                "auto_pruning.prune_preceding_on_non_green", True
            )
        )
        prune_validation = bool(
            self._config_service.get_setting(
                "auto_pruning.prune_validation_failures", True
            )
        )

        for item in items:
            if item.scope != "Turn":
                continue

            # Match numeric turn directories (e.g. '01', '02')
            turn_id = self._extract_turn_id(item.path)
            if not turn_id:
                continue

            reason = self._check_item_for_pruning(
                item, prune_non_green, prune_validation
            )
            if reason:
                if reason == "Pruned as it led to a non-green state":
                    try:
                        target = int(turn_id) - 1
                        if target > 0:
                            # Use unpadded string as key for better normalization
                            turns_to_prune[str(target)] = reason
                    except (ValueError, TypeError):
                        pass
                else:
                    turns_to_prune[turn_id] = reason

        return turns_to_prune

    def _check_item_for_pruning(
        self, item: Any, prune_non_green: bool, prune_validation: bool
    ) -> Optional[str]:
        """Evaluates an individual item for content-based pruning heuristics."""
        try:
            # Heuristic 3: Non-green state
            if prune_non_green and item.path.endswith("plan.md"):
                content = self._file_system_manager.read_file(item.path)
                if "🔴" in content or "🟡" in content:
                    return "Pruned as it led to a non-green state"

            # Heuristic 4: Validation failure
            if prune_validation and item.path.endswith("report.md"):
                content = self._file_system_manager.read_file(item.path)
                if "Validation Failed" in content:
                    return "Plan failed validation"
        except (FileNotFoundError, OSError):
            # On Windows, rapid read-after-write can throw PermissionError
            return None
        return None

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
