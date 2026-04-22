from __future__ import annotations
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from teddy_executor.core.domain.models.change_set import ChangeSet
from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.ports.outbound import (
        IFileSystemManager,
        IConfigService,
    )
    from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator


class ActionChangeSetBuilder:
    """
    Shared service to build ChangeSet objects for CREATE and EDIT actions.
    Ensures DRY logic between executors and reviewers.
    """

    @staticmethod
    def format_action_prompt(action: "ActionData") -> str:
        """Generates a detailed prompt string for an action."""
        prompt_parts = [
            "---",
            f"Action: {action.type}",
            f"Description: {action.description}" if action.description else "",
        ]
        display_map = {"handoff_resources": "Reference Files"}
        param_str = "\n".join(
            f"  - {display_map.get(k, k)}: {v}"
            for k, v in action.params.items()
            if k.lower() not in ("edits", "content")
        )
        if param_str:
            prompt_parts.extend(["Parameters:", param_str])
        prompt_parts.append("---")
        return "\n".join(filter(None, prompt_parts))

    def __init__(
        self,
        file_system_manager: IFileSystemManager,
        config_service: IConfigService,
        edit_simulator: IEditSimulator,
    ):
        self._file_system_manager = file_system_manager
        self._config_service = config_service
        self._edit_simulator = edit_simulator

    def create_change_set(self, action: "ActionData") -> Optional[ChangeSet]:
        """Creates a ChangeSet for file operations."""
        action_type = action.type.upper()
        if action_type not in ("CREATE", "EDIT"):
            return None

        path_str = action.params.get("path") or action.params.get("File Path")
        if not path_str:
            return None

        before_content = (
            self._file_system_manager.read_file(path_str)
            if self._file_system_manager.path_exists(path_str)
            else ""
        )
        path = Path(path_str)

        if action_type == "EDIT":
            global_threshold_raw = self._config_service.get_setting(
                "execution.similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD
            )
            global_threshold = (
                float(global_threshold_raw)
                if global_threshold_raw is not None
                else DEFAULT_SIMILARITY_THRESHOLD
            )

            threshold_raw = action.params.get(
                "execution.similarity_threshold", global_threshold
            )
            threshold = (
                float(threshold_raw) if threshold_raw is not None else global_threshold
            )

            match_all = action.params.get("match_all", False)
            after_content, _ = self._edit_simulator.simulate_edits(
                before_content,
                action.params.get("edits", []),
                threshold=threshold,
                match_all=match_all,
            )
        else:  # CREATE
            after_content = action.params.get("content", "")

        return ChangeSet(
            path=path,
            before_content=before_content,
            after_content=after_content,
            action_type=action_type,
        )
