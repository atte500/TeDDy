from typing import List, Dict, Any
import yaml

from teddy.core.domain.models import (
    Action,
    Plan,
    ActionResult,
    ExecutionReport,
)
from teddy.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy.core.ports.outbound.shell_executor import ShellExecutor
from teddy.core.ports.outbound.file_system_manager import FileSystemManager


class PlanService(RunPlanUseCase):
    def __init__(
        self, shell_executor: ShellExecutor, file_system_manager: FileSystemManager
    ):
        self.shell_executor = shell_executor
        self.file_system_manager = file_system_manager

    def _parse_plan_content(self, plan_content: str) -> List[Dict[str, Any]]:
        """Parses the raw YAML string into a list of action dictionaries."""
        try:
            parsed_yaml = yaml.safe_load(plan_content)
            if not isinstance(parsed_yaml, list):
                raise yaml.YAMLError("Plan content must be a YAML list of actions.")
            return parsed_yaml
        except yaml.YAMLError:
            # Re-raise a more specific error if needed, or handle here.
            # For now, we'll let it propagate up to the main execute method.
            raise

    def _execute_single_action(self, action: Action) -> ActionResult:
        """Executes one action and returns its result."""
        if action.action_type == "execute":
            command = action.params["command"]
            command_result = self.shell_executor.run(command)
            status = "SUCCESS" if command_result.return_code == 0 else "FAILURE"
            return ActionResult(
                action=action,
                status=status,
                output=command_result.stdout,
                error=command_result.stderr,
            )
        elif action.action_type == "create_file":
            file_path = action.params["file_path"]
            content = action.params["content"]
            try:
                self.file_system_manager.create_file(path=file_path, content=content)
                return ActionResult(
                    action=action,
                    status="COMPLETED",
                    output=f"Created file: {file_path}",
                )
            except FileExistsError as e:
                error_message = f"{e.strerror}: '{e.filename}'"
                return ActionResult(
                    action=action, status="FAILURE", error=error_message
                )

        # This part should ideally not be reached due to domain model validation
        return ActionResult(
            action=action,
            status="FAILURE",
            output=None,
            error=f"Unhandled action type: {action.action_type}",
        )

    def execute(self, plan_content: str) -> ExecutionReport:
        report = ExecutionReport()
        try:
            # 1. Parse and Validate Input
            parsed_actions = self._parse_plan_content(plan_content)

            # 2. Create Domain Objects
            actions = [
                Action(action_type=item["action"], params=item.get("params", {}))
                for item in parsed_actions
            ]
            plan = Plan(actions=actions)

            # 3. Execute Actions
            for action in plan.actions:
                result = self._execute_single_action(action)
                report.action_logs.append(result)

        except (yaml.YAMLError, ValueError) as e:
            # Catches parsing errors from YAML or validation errors from domain objects
            parsing_error_action = Action(action_type="parse_plan", params={})
            action_result = ActionResult(
                action=parsing_error_action,
                status="FAILURE",
                output=None,
                error=f"Failed to process plan: {e}",
            )
            report.action_logs.append(action_result)

        # Finalize the report summary
        overall_status = "SUCCESS"
        if any(log.status == "FAILURE" for log in report.action_logs):
            overall_status = "FAILURE"
        report.run_summary["status"] = overall_status

        return report
