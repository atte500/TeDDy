import re
from datetime import datetime, timezone
from pathlib import Path
import yaml
from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.plan import ActionType
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.prompts import find_prompt_content


class SessionService(ISessionManager):
    """
    Service for managing session directories and metadata.
    """

    def __init__(self, file_system_manager: FileSystemManager):
        self._file_system_manager = file_system_manager

    def create_session(self, name: str, agent_name: str) -> str:
        """
        Initializes a new session directory and bootstraps it for Turn 1.
        """
        session_root = f".teddy/sessions/{name}"
        turn_dir = f"{session_root}/01"

        self._file_system_manager.create_directory(turn_dir)

        # 1. Seed session.context from init.context
        init_context = self._file_system_manager.read_file(".teddy/init.context")
        # Strip comments as per specification
        clean_context = "\n".join(
            [
                line
                for line in init_context.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        )
        self._file_system_manager.write_file(
            f"{session_root}/session.context", clean_context
        )

        # 2. Populate system_prompt.xml
        prompt_content = find_prompt_content(agent_name)
        if not prompt_content:
            raise ValueError(f"Agent prompt '{agent_name}' not found.")
        self._file_system_manager.write_file(
            f"{turn_dir}/system_prompt.xml", prompt_content
        )

        # 3. Create meta.yaml
        meta_data = {
            "turn_id": "01",
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._file_system_manager.write_file(
            f"{turn_dir}/meta.yaml", yaml.dump(meta_data)
        )

        return session_root

    def get_latest_turn(self, session_name: str) -> str:
        """
        Identifies and returns the latest turn directory in the specified session.
        """
        session_root = f".teddy/sessions/{session_name}"
        try:
            items = self._file_system_manager.list_directory(session_root)
        except FileNotFoundError:
            raise ValueError(f"Session '{session_name}' not found.")

        # Filter for zero-padded numeric directories (e.g., '01', '02')
        turns = [item for item in items if item.isdigit()]
        if not turns:
            raise ValueError(f"No turns found in session '{session_name}'.")

        latest_turn_id = sorted(turns)[-1]
        return f"{session_root}/{latest_turn_id}"

    def _extract_resource_path(self, resource_str: str) -> str:
        """Extracts the path from a Markdown link or returns the string if not a link."""
        match = re.search(r"\[.*\]\((.*)\)", resource_str)
        if match:
            path = match.group(1)
            return path.lstrip("/")
        return resource_str.strip()

    def transition_to_next_turn(
        self, plan_path: str, execution_report: ExecutionReport
    ) -> str:
        """
        Calculates and creates the next turn directory based on the current turn
        and the outcome of its plan.
        """
        current_turn_dir = Path(plan_path).parent.as_posix()
        session_dir = Path(current_turn_dir).parent.as_posix()

        # 1. Read current metadata and context
        meta_content = self._file_system_manager.read_file(
            f"{current_turn_dir}/meta.yaml"
        )
        current_meta = yaml.safe_load(meta_content) or {}
        current_turn_id = current_meta.get("turn_id")

        context_content = self._file_system_manager.read_file(
            f"{current_turn_dir}/turn.context"
        )
        # Seed next context with current context (minus empty lines)
        next_context_paths = {
            line.strip() for line in context_content.splitlines() if line.strip()
        }

        # 2. Calculate next turn
        current_turn_num = int(Path(current_turn_dir).name)
        next_turn_num = current_turn_num + 1
        next_turn_id = f"{next_turn_num:02d}"
        next_turn_dir = f"{session_dir}/{next_turn_id}"

        # 3. Initialize next turn directory
        self._file_system_manager.create_directory(next_turn_dir)

        # 4. Copy system_prompt.xml
        prompt_content = self._file_system_manager.read_file(
            f"{current_turn_dir}/system_prompt.xml"
        )
        self._file_system_manager.write_file(
            f"{next_turn_dir}/system_prompt.xml", prompt_content
        )

        # 5. Create next meta.yaml
        next_meta = {
            "turn_id": next_turn_id,
            "parent_turn_id": current_turn_id,
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._file_system_manager.write_file(
            f"{next_turn_dir}/meta.yaml", yaml.dump(next_meta)
        )

        # 6. Apply READ/PRUNE side effects
        for action in execution_report.original_actions:
            resource = action.params.get("resource") or action.params.get("Resource")
            if not resource:
                continue

            extracted_path = self._extract_resource_path(resource)
            if action.type == ActionType.READ.value:
                next_context_paths.add(extracted_path)
            elif action.type == ActionType.PRUNE.value:
                next_context_paths.discard(extracted_path)

        # 7. Add current report.md to next context
        relative_report_path = f"{Path(current_turn_dir).name}/report.md"
        next_context_paths.add(relative_report_path)

        # 8. Write next turn.context
        sorted_paths = sorted(list(next_context_paths))
        self._file_system_manager.write_file(
            f"{next_turn_dir}/turn.context", "\n".join(sorted_paths)
        )

        return next_turn_dir
