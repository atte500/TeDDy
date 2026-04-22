from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from teddy_executor.core.ports.outbound.session_manager import ISessionManager
    from teddy_executor.core.ports.outbound.markdown_report_formatter import (
        IMarkdownReportFormatter,
    )
    from teddy_executor.core.services.session_planner import SessionPlanner
    from teddy_executor.core.services.session_replanner import SessionReplanner

from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


@dataclass(frozen=True)
class PlanningPorts:
    """Outbound ports required by the PlanningService."""

    context: IGetContextUseCase
    llm: ILlmClient
    fs: IFileSystemManager
    config: IConfigService
    prompts: IPromptManager
    ui: IUserInteractor


@dataclass(frozen=True)
class SessionPorts:
    """Ports required by the SessionLifecycleManager."""

    session_service: "ISessionManager"
    file_system_manager: "IFileSystemManager"
    report_formatter: "IMarkdownReportFormatter"
    user_interactor: "IUserInteractor"
    session_planner: "SessionPlanner"
    replanner: "SessionReplanner"
