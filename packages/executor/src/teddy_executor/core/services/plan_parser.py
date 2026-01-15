from pathlib import Path
import yaml

from teddy_executor.core.domain.models import ActionData, V2_Plan
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager


class PlanParser:
    """
    A service responsible for parsing a plan file into a structured domain object.
    """

    def __init__(self, file_system_manager: FileSystemManager):
        """
        Initializes the PlanParser with its dependencies.

        Args:
            file_system_manager: An adapter for the IFileSystemManager port.
        """
        self._file_system_manager = file_system_manager

    def parse(self, plan_path: Path) -> V2_Plan:
        """
        Reads and parses the specified YAML plan file.

        Args:
            plan_path: The path to the plan file.

        Returns:
            A V2_Plan domain object representing the validated plan.

        Raises:
            PlanNotFoundError: If the file does not exist at the given path.
            InvalidPlanError: If the file content is not valid YAML or
                              if it does not conform to the expected plan structure.
        """
        # Note: Exception handling will be added in subsequent TDD cycles.
        raw_content = self._file_system_manager.read_file(str(plan_path))
        parsed_yaml = yaml.safe_load(raw_content)

        actions_data = []
        # Gracefully handle empty or malformed plan files
        if parsed_yaml and isinstance(parsed_yaml.get("actions"), list):
            for action_dict in parsed_yaml["actions"]:
                action_type = action_dict.pop("type")
                actions_data.append(ActionData(type=action_type, params=action_dict))

        return V2_Plan(actions=actions_data)
