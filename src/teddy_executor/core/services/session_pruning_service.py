import re
from dataclasses import is_dataclass, replace
from typing import Any, Dict, Optional, Set

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
        if not self._config_service.get_setting("auto_pruning.enabled", True):
            return context

        # Handle MagicMocks in unit tests
        if not is_dataclass(context):
            return context

        items = list(context.items)
        pruned_indices: Set[int] = set()

        # 1. Prune by status/validation failure (Heuristics 3 & 4)
        turns_to_prune = self._identify_turns_to_prune(items)

        for i, item in enumerate(items):
            if item.scope != "Turn":
                continue

            if item.git_status == "D":
                pruned_indices.add(i)
                items[i] = replace(
                    item, selected=False, auto_prune_reason="File deleted from disk"
                )
                continue

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
                pruned_indices.add(i)
                items[i] = replace(
                    item,
                    selected=False,
                    auto_prune_reason="Pruned as it exceeds individual threshold",
                )
                continue

            # Match numeric turn directories (e.g. '01', '02')
            match = re.search(r"/(\d+)/", item.path)
            turn_id = match.group(1) if match else None
            if turn_id and turn_id in turns_to_prune:
                pruned_indices.add(i)
                items[i] = replace(
                    item,
                    selected=False,
                    auto_prune_reason=turns_to_prune[turn_id],
                )

        # 2. Heuristic 2: Global Budget
        items = self._apply_global_budget(items)

        return replace(context, items=items)

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
            match = re.search(r"/(\d+)/", item.path)
            if not match:
                continue
            turn_id = match.group(1)

            reason = self._check_item_for_pruning(
                item, prune_non_green, prune_validation
            )
            if reason:
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
                if "Status: Validation Failed" in content:
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
