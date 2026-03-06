from datetime import datetime, timezone
import yaml
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

    def get_latest_turn(self, _session_name: str) -> str:
        """
        Identifies and returns the latest turn directory in the specified session.
        """
        raise NotImplementedError()
