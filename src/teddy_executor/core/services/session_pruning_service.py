import logging
import re
from dataclasses import is_dataclass, replace
from typing import Any, Dict, Optional

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.utils.paths import normalize_resource_path

_BUDGET_PRUNE_REASON = "Pruned to fit context budget"
_RECORD_FILENAMES = frozenset({"plan.md", "report.md"})

logger = logging.getLogger(__name__)


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

            # 1. Prune turns whose report failed validation
            turns_to_prune = self._identify_turns_to_prune(items, current_status)

            for i, item in enumerate(items):
                new_item = self._process_context_item(item, turns_to_prune)
                if new_item is not item:
                    items[i] = new_item

            # 2. Heuristic 6: Retention Limit
            items = self._apply_retention_limit(items, self._read_retention_batch())

            # 3. Heuristic 2: Global Budget
            items = self._apply_global_budget(
                items,
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

        # Normalize path for consistent string matching (link-aware)
        posix_path = normalize_resource_path(item.path)

        # Match numeric turn directories (e.g. '01', '02')
        turn_id = self._extract_turn_id(posix_path)
        if turn_id:
            # Producers key on the unpadded id, so a padded directory normalizes.
            reason = turns_to_prune.get(str(int(turn_id)))
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
        # Normalize to forward slashes and strip prefixes for consistent matching (link-aware)
        normalized = normalize_resource_path(path)
        # Turn IDs are typically 1-3 digits. 4+ digits usually represent years or other data.
        matches = re.findall(r"(?:^|/)(\d{1,3})(?=/|$)", normalized)
        return matches[-1] if matches else None

    def _identify_turns_to_prune(
        self, items, current_status: Optional[str] = None
    ) -> Dict[str, str]:
        """Identifies the turns to prune because their report failed validation."""
        prune_validation = bool(
            self._config_service.get_setting(
                "auto_pruning.prune_validation_failures", True
            )
        )

        validation_failures, non_vf_reports = self._collect_turn_metadata(
            items, prune_validation
        )

        return self._apply_pruning_heuristics(
            validation_failures,
            current_status,
            non_vf_reports,
        )

    def _collect_turn_metadata(
        self,
        items,
        prune_validation: bool,
    ) -> tuple[set[int], set[int]]:
        """Collects the turns that failed validation and the turns that did not.

        Only a ``report.md`` carries either fact, so a plan is never read here.
        """
        validation_failures: set[int] = set()
        non_vf_reports: set[int] = set()
        checked_paths = set()

        for item in items:
            if item.scope != "Turn" or item.path in checked_paths:
                continue

            posix_path = item.path.replace("\\", "/")
            if not posix_path.endswith("report.md"):
                continue

            turn_id_str = self._extract_turn_id(posix_path)
            if not turn_id_str:
                continue

            turn_id = int(turn_id_str)
            checked_paths.add(item.path)

            if prune_validation and self._check_report_failed_validation(item.path):
                validation_failures.add(turn_id)

            if self._check_report_is_non_vf_report(item.path):
                non_vf_reports.add(turn_id)

        return validation_failures, non_vf_reports

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

    def _check_report_is_non_vf_report(self, path: str) -> bool:
        """Checks if a report file exists and does NOT have validation failure status."""
        content = self._safe_read(path)
        if content:
            return not bool(
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
        validation_failures: set[int],
        current_status: Optional[str] = None,
        non_vf_reports: Optional[set[int]] = None,
    ) -> Dict[str, str]:
        """Applies the validation-failure heuristic to the collected metadata."""
        turns_to_prune: Dict[str, str] = {}

        # A validation failure is pruned only once a non-validation turn follows it.
        is_currently_non_vf = (
            current_status is not None and "Validation Failed" not in current_status
        )
        latest_non_vf_turn = max(non_vf_reports) if non_vf_reports else -1

        for tid in sorted(validation_failures):
            prune_vf = tid < latest_non_vf_turn
            if not prune_vf and is_currently_non_vf:
                prune_vf = True
            if prune_vf:
                turns_to_prune[str(tid)] = "Plan failed validation"

        return turns_to_prune

    def _read_retention_batch(self) -> int:
        """Read the retention batch, the drop size once the ceiling is exceeded.

        The batch counts how many of the oldest turns fall together; it never
        sets the retained depth, which is ``max_turns_retention``. A missing
        setting falls back to one, keeping the per-turn cadence that predates
        batching. A non-positive or unparseable value also falls back to one but
        logs a warning, because a bad setting must not silently disable
        retention.
        """
        raw = self._config_service.get_setting("auto_pruning.retention_batch", 1)
        if raw is None:
            return 1
        try:
            batch = int(raw)
        except (TypeError, ValueError):
            logger.warning(
                "Unparseable auto_pruning.retention_batch %r; falling back to 1.",
                raw,
            )
            return 1
        if batch < 1:
            logger.warning(
                "auto_pruning.retention_batch must be at least 1, got %r; "
                "falling back to 1.",
                raw,
            )
            return 1
        return batch

    def _apply_retention_limit(self, items, retention_batch: int):
        """Keeps the turn-scoped history inside ``max_turns_retention`` turns.

        ``max_turns_retention`` is a ceiling on how many distinct turns the
        turn-scoped context may hold, and ``retention_batch`` is how many of the
        oldest turns fall together once that ceiling is exceeded. At or below the
        ceiling nothing is deselected. Past it, only the newest
        ``max(1, max_turns_retention - retention_batch + 1)`` turns survive, so
        one extra turn drops a whole batch and a larger overage drops that
        overage plus a full batch, minus one. Counting distinct turn ids keeps a
        sparse history honest, and clamping to one keeps the newest turn alive
        even when the batch meets or exceeds the ceiling. A batch of one retains
        the newest ``max_turns_retention`` turns, reproducing the per-turn
        cadence that predates batching.
        """
        assert retention_batch >= 1, (
            "retention_batch must be at least 1 to keep retention enabled"
        )
        try:
            setting = self._config_service.get_setting(
                "auto_pruning.max_turns_retention", 0
            )
            limit = int(setting) if setting is not None else 0
        except (TypeError, ValueError):
            limit = 0

        if limit <= 0:
            return items

        turn_id_map = self._map_turn_ids(items)
        selected_ids = sorted(
            {turn_id for idx, turn_id in turn_id_map.items() if items[idx].selected}
        )
        if len(selected_ids) <= limit:
            return items

        retained_count = max(1, limit - retention_batch + 1)
        retained_ids = set(selected_ids[-retained_count:])
        reason = f"Turn exceeds retention limit of {limit}"

        for idx, turn_id in turn_id_map.items():
            if turn_id in retained_ids or not items[idx].selected:
                continue
            items[idx] = replace(
                items[idx],
                selected=False,
                auto_prune_reason=reason,
            )

        return items

    def _map_turn_ids(self, items) -> Dict[int, int]:
        """Maps each item index carrying a turn id to that id."""
        turn_id_map: Dict[int, int] = {}

        for i, item in enumerate(items):
            if item.scope != "Turn":
                continue

            tid_str = self._extract_turn_id(item.path)
            if tid_str:
                try:
                    turn_id_map[i] = int(tid_str)
                except (ValueError, TypeError):
                    continue
        return turn_id_map

    def _get_turn_context_threshold(self) -> int:
        """Reads the turn context threshold from config.

        Reads ``auto_pruning.turn_context_threshold`` from config.
        Returns 0 if not set or on parse errors (skips budget heuristic).
        """
        try:
            threshold = self._config_service.get_setting(
                "auto_pruning.turn_context_threshold"
            )
            return int(threshold) if threshold is not None else 0
        except (TypeError, ValueError):
            return 0

    def _apply_global_budget(self, items):
        """Deselects turn-scope files until their total fits the token budget.

        Victims are ranked by what losing each file costs, not by size alone. A
        copy of a project file leaves first, largest-first inside that class,
        because a single ``READ`` restores it. Once no copy remains, the oldest
        retained turn leaves with its whole record set, because a turn's plan and
        its report are one record: nothing re-renders either, and a plan without
        its report is unrecoverable reasoning.
        """
        threshold = self._get_turn_context_threshold()
        if threshold <= 0:
            return items

        total_tokens = sum(
            item.token_count for _, item in self._iter_budget_candidates(items)
        )
        if total_tokens <= threshold:
            return items

        copies, turns = self._rank_budget_candidates(items)

        for idx, item in copies:
            if total_tokens <= threshold:
                break
            items[idx] = replace(
                item, selected=False, auto_prune_reason=_BUDGET_PRUNE_REASON
            )
            total_tokens -= item.token_count

        for turn_id in sorted(turns):
            if total_tokens <= threshold:
                break
            for idx, item in turns[turn_id]:
                items[idx] = replace(
                    items[idx], selected=False, auto_prune_reason=_BUDGET_PRUNE_REASON
                )
                total_tokens -= item.token_count

        return items

    def _iter_budget_candidates(self, items):
        """Yields the ``(index, item)`` pairs the budget may deselect.

        Only a selected ``Turn``-scope item carrying a numeric token count is a
        candidate: session-scope files and the system prompt sit outside the
        budget by spec.
        """
        for idx, item in enumerate(items):
            if item.scope != "Turn" or not item.selected:
                continue
            if not isinstance(item.token_count, (int, float)):
                continue
            yield idx, item

    def _rank_budget_candidates(self, items):
        """Splits the budget candidates into copies and turns.

        ``copies`` returns largest-first, and a tie keeps its manifest order
        because ``sorted`` is stable. ``turns`` groups each record set under its
        turn id so the caller can drop the whole set at once, oldest first.
        """
        copies: list[tuple[int, Any]] = []
        turns: Dict[int, list[tuple[int, Any]]] = {}
        for idx, item in self._iter_budget_candidates(items):
            turn_id = self._record_turn_id(item.path)
            if turn_id is None:
                copies.append((idx, item))
            else:
                turns.setdefault(turn_id, []).append((idx, item))
        copies.sort(key=lambda candidate: candidate[1].token_count, reverse=True)
        return copies, turns

    def _record_turn_id(self, path: str) -> Optional[int]:
        """Returns the turn id when ``path`` is a turn record, else ``None``.

        A record is a ``plan.md`` or ``report.md`` under a numeric turn
        directory: nothing re-renders it, so losing it loses reasoning. Every
        other path is a restorable copy, including a project file that happens
        to be named ``plan.md`` somewhere else in the tree.
        """
        posix_path = normalize_resource_path(path)
        if posix_path.rsplit("/", 1)[-1] not in _RECORD_FILENAMES:
            return None
        turn_id = self._extract_turn_id(posix_path)
        return int(turn_id) if turn_id is not None else None
