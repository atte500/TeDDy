from typing import Optional
from teddy_executor.core.domain.models import (
    ActionLog,
    ActionStatus,
    ChangeSet,
)
from teddy_executor.core.utils.diff import generate_unified_diff

# Constant for perfect match detection to avoid floating point noise
PERFECT_MATCH_THRESHOLD = 0.99999


class ActionDiffManager:
    """Helper class to manage diff injection and suppression logic."""

    @staticmethod
    def inject_diff(
        action, action_log: ActionLog, change_set: Optional[ChangeSet]
    ) -> ActionLog:
        """Injects or suppresses diffs in the ActionLog based on outcome."""
        if ActionDiffManager._should_suppress(action, action_log, change_set):
            return ActionDiffManager._clean_log(action_log)

        diff = ActionDiffManager._generate_diff(action, change_set)
        if not diff:
            return action_log

        details = action_log.details
        new_details = {"diff": diff}
        if isinstance(details, dict):
            new_details.update(details)

        return ActionLog(
            status=action_log.status,
            action_type=action_log.action_type,
            params=action_log.params,
            details=new_details,
        )

    @staticmethod
    def _should_suppress(
        action, action_log: ActionLog, change_set: Optional[ChangeSet]
    ) -> bool:
        """Determines if a diff should be suppressed."""
        if action_log.status != ActionStatus.SUCCESS:
            return True

        is_create_ovr = (
            action.type.upper() == "CREATE"
            and (action.params.get("overwrite") or action.params.get("Overwrite"))
            and change_set
            and change_set.before_content
        )
        is_edit = action.type.upper() == "EDIT"

        if not (is_create_ovr or is_edit):
            return True

        if is_edit:
            details = action_log.details
            if not isinstance(details, dict):
                return True
            scores = details.get("similarity_scores") or [
                details.get("similarity_score", 1.0)
            ]
            if all(s >= PERFECT_MATCH_THRESHOLD for s in scores):
                return True

        return not (
            change_set
            and isinstance(change_set.before_content, str)
            and isinstance(change_set.after_content, str)
        )

    @staticmethod
    def _clean_log(action_log: ActionLog) -> ActionLog:
        """Removes pre-injected diffs from the log."""
        if isinstance(action_log.details, dict) and "diff" in action_log.details:
            new_details = action_log.details.copy()
            new_details.pop("diff")
            return ActionLog(
                status=action_log.status,
                action_type=action_log.action_type,
                params=action_log.params,
                details=new_details,
            )
        return action_log

    @staticmethod
    def _generate_diff(action, change_set: Optional[ChangeSet]) -> Optional[str]:
        """Generates the actual diff string."""
        if not change_set:
            return None

        from teddy_executor.core.utils.diff import generate_character_diff

        if action.type.upper() == "EDIT":
            return generate_character_diff(
                change_set.before_content, change_set.after_content
            )

        return generate_unified_diff(
            change_set.before_content,
            change_set.after_content,
            change_set.path.name,
        )
