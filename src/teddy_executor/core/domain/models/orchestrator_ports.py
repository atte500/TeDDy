from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
    from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
    from teddy_executor.core.ports.outbound import IFileSystemManager, IUserInteractor
    from teddy_executor.core.ports.outbound.execution_report_assembler import (
        IExecutionReportAssembler,
    )
    from teddy_executor.core.services.action_executor import ActionExecutor


@dataclass(frozen=True)
class OrchestratorPorts:
    """Groups dependencies for the ExecutionOrchestrator."""

    plan_parser: IPlanParser
    plan_validator: IPlanValidator
    action_executor: ActionExecutor
    file_system_manager: IFileSystemManager
    report_assembler: IExecutionReportAssembler
    user_interactor: IUserInteractor
    plan_reviewer: Optional[IPlanReviewer] = None
