from typing import List, Dict, Any
import json
from dataclasses import asdict
import yaml
from datetime import datetime, timezone
from requests.exceptions import RequestException

from teddy_executor.core.domain.models import (
    Action,
    Plan,
    ActionResult,
    ExecutionReport,
    ExecuteAction,
    CreateFileAction,
    ReadAction,
    EditAction,
    ChatWithUserAction,
    ResearchAction,
    SERPReport,
    SearchTextNotFoundError,
    FileAlreadyExistsError,
    MultipleMatchesFoundError,
    WebSearchError,
)
from teddy_executor.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.ports.outbound.web_scraper import WebScraper
from teddy_executor.core.ports.outbound.user_interactor import UserInteractor
from teddy_executor.core.ports.outbound.web_searcher import IWebSearcher
from teddy_executor.core.services.action_factory import ActionFactory


class PlanService(RunPlanUseCase):
    def __init__(
        self,
        shell_executor: IShellExecutor,
        file_system_manager: FileSystemManager,
        action_factory: ActionFactory,
        web_scraper: WebScraper,
        user_interactor: "UserInteractor",
        web_searcher: "IWebSearcher",
    ):
        self.shell_executor = shell_executor
        self.file_system_manager = file_system_manager
        self.action_factory = action_factory
        self.web_scraper = web_scraper
        self.user_interactor = user_interactor
        self.web_searcher = web_searcher
        self.action_handlers = {
            ExecuteAction: self._handle_execute,
            CreateFileAction: self._handle_create_file,
            ReadAction: self._handle_read,
            EditAction: self._handle_edit,
            ChatWithUserAction: self._handle_chat_with_user,
            ResearchAction: self._handle_research,
        }

    def _format_action_for_prompt(self, action: Action, index: int, total: int) -> str:
        """Formats an action into a user-friendly string for confirmation."""
        header = f"Action {index}/{total}: {action.action_type}"
        params = asdict(action)
        params.pop("action_type", None)
        param_lines = [f"  {k}: {v}" for k, v in params.items()]
        return "\n".join([header] + param_lines)

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
        try:
            command_result = self.shell_executor.execute(
                command=action.command, cwd=action.cwd, env=action.env
            )
            status = "SUCCESS" if command_result.return_code == 0 else "FAILURE"
            return ActionResult(
                action=action,
                status=status,
                output=command_result.stdout,
                error=command_result.stderr,
            )
        except (ValueError, FileNotFoundError) as e:
            return ActionResult(action=action, status="FAILURE", error=str(e))

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
        except FileAlreadyExistsError as e:
            # The file exists, so we read its content to return in the report.
            content = self.file_system_manager.read_file(path=e.file_path)
            return ActionResult(
                action=action,
                status="FAILURE",
                error=str(e),
                output=content,
            )

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
        except MultipleMatchesFoundError as e:
            return ActionResult(
                action=action,
                status="FAILURE",
                error=str(e),
                output=e.content,
            )

    def _handle_chat_with_user(self, action: ChatWithUserAction) -> ActionResult:
        response = self.user_interactor.ask_question(prompt=action.prompt)
        return ActionResult(action=action, status="SUCCESS", output=response)

    def _serialize_serp_report(self, report: SERPReport) -> str:
        """Serializes a SERPReport object to a JSON string."""
        return json.dumps(asdict(report), indent=2)

    def _handle_research(self, action: ResearchAction) -> ActionResult:
        try:
            serp_report = self.web_searcher.search(queries=action.queries)
            json_output = self._serialize_serp_report(serp_report)
            return ActionResult(action=action, status="SUCCESS", output=json_output)
        except WebSearchError as e:
            return ActionResult(action=action, status="FAILURE", error=str(e))
        except Exception as e:
            return ActionResult(
                action=action,
                status="FAILURE",
                error=f"An unexpected error occurred during research: {e}",
            )

    def _execute_single_action(self, action: Action) -> ActionResult:
        """Executes one action by looking up its handler in the dispatch map."""
        handler = self.action_handlers.get(type(action))
        if handler:
            return handler(action)  # type: ignore[operator]

        return ActionResult(
            action=action,
            status="FAILURE",
            error=f"Unhandled action type: {type(action).__name__}",
        )

    def execute(self, plan_content: str, auto_approve: bool = False) -> ExecutionReport:
        report = ExecutionReport()
        start_time_utc = datetime.now(timezone.utc).isoformat()

        try:
            # 1. Parse and Validate Input
            parsed_actions = self._parse_plan_content(plan_content)

            # 2. Create Domain Objects
            actions = [
                self.action_factory.create_action(item) for item in parsed_actions
            ]
            plan = Plan(actions=actions)

            # 3. Execute Actions
            total_actions = len(plan.actions)
            for i, action in enumerate(plan.actions):
                if not auto_approve:
                    prompt = self._format_action_for_prompt(
                        action, index=i + 1, total=total_actions
                    )
                    approved, reason = self.user_interactor.confirm_action(prompt)
                    if not approved:
                        result = ActionResult(
                            action=action, status="SKIPPED", reason=reason
                        )
                        report.action_logs.append(result)
                        continue

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
        report.run_summary["start_time"] = start_time_utc

        return report
