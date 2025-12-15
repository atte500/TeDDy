from typing import List, Dict, Any
import yaml
from requests.exceptions import RequestException

from teddy.core.domain.models import (
    Action,
    Plan,
    ActionResult,
    ExecutionReport,
    ExecuteAction,
    CreateFileAction,
    ReadAction,
    EditAction,
    SearchTextNotFoundError,
)
from teddy.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy.core.ports.outbound.shell_executor import ShellExecutor
from teddy.core.ports.outbound.file_system_manager import FileSystemManager
from teddy.core.ports.outbound.web_scraper import WebScraper
from teddy.core.services.action_factory import ActionFactory


class PlanService(RunPlanUseCase):
    def __init__(
        self,
        shell_executor: ShellExecutor,
        file_system_manager: FileSystemManager,
        action_factory: ActionFactory,
        web_scraper: WebScraper,
    ):
        self.shell_executor = shell_executor
        self.file_system_manager = file_system_manager
        self.action_factory = action_factory
        self.web_scraper = web_scraper

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

    def _handle_execute(self, action: ExecuteAction) -> ActionResult:
        command_result = self.shell_executor.run(action.command)
        status = "SUCCESS" if command_result.return_code == 0 else "FAILURE"
        return ActionResult(
            action=action,
            status=status,
            output=command_result.stdout,
            error=command_result.stderr,
        )

    def _handle_create_file(self, action: CreateFileAction) -> ActionResult:
        try:
            self.file_system_manager.create_file(
                path=action.file_path, content=action.content
            )
            return ActionResult(
                action=action,
                status="COMPLETED",
                output=f"Created file: {action.file_path}",
            )
        except FileExistsError as e:
            error_message = f"{e.strerror}: '{e.filename}'"
            return ActionResult(action=action, status="FAILURE", error=error_message)

    def _handle_read(self, action: ReadAction) -> ActionResult:
        try:
            if action.is_remote():
                content = self.web_scraper.get_content(url=action.source)
            else:
                content = self.file_system_manager.read_file(path=action.source)
            return ActionResult(action=action, status="SUCCESS", output=content)
        except (FileNotFoundError, RequestException) as e:
            return ActionResult(action=action, status="FAILURE", error=str(e))

    def _handle_edit(self, action: EditAction) -> ActionResult:
        try:
            self.file_system_manager.edit_file(
                path=action.file_path, find=action.find, replace=action.replace
            )
            return ActionResult(
                action=action,
                status="COMPLETED",
                output=f"Edited file: {action.file_path}",
            )
        except FileNotFoundError as e:
            return ActionResult(action=action, status="FAILURE", error=str(e))
        except SearchTextNotFoundError as e:
            return ActionResult(
                action=action,
                status="FAILURE",
                error=str(e),
                output=e.content,
            )

    def _execute_single_action(self, action: Action) -> ActionResult:
        """Executes one action and returns its result."""
        if isinstance(action, ExecuteAction):
            return self._handle_execute(action)
        elif isinstance(action, CreateFileAction):
            return self._handle_create_file(action)
        elif isinstance(action, ReadAction):
            return self._handle_read(action)
        elif isinstance(action, EditAction):
            return self._handle_edit(action)

        return ActionResult(
            action=action,
            status="FAILURE",
            output=None,
            error=f"Unhandled action type: {type(action).__name__}",
        )

    def execute(self, plan_content: str) -> ExecutionReport:
        report = ExecutionReport()
        try:
            # 1. Parse and Validate Input
            parsed_actions = self._parse_plan_content(plan_content)

            # 2. Create Domain Objects
            actions = [
                self.action_factory.create_action(item) for item in parsed_actions
            ]
            plan = Plan(actions=actions)

            # 3. Execute Actions
            for action in plan.actions:
                result = self._execute_single_action(action)
                report.action_logs.append(result)

        except (yaml.YAMLError, ValueError) as e:
            # Catches parsing errors from YAML or validation errors from domain objects
            parsing_error_action = self.action_factory.create_action(
                {"action": "parse_plan", "params": {}}
            )
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
