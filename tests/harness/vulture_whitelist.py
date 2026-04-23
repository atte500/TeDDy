"""
Vulture Whitelist: Reference-Based Dead Code Suppression

This module prevents Vulture from incorrectly flagging Domain Types and Interfaces
as dead code. It uses a simple "Import and Alias" pattern. By importing the entity,
Mypy verifies that the code actually exists (preventing the whitelist from rotting).
By aliasing it, Vulture registers the name as used globally.

Note: Dynamic framework callbacks (like Textual's on_* or action_*) should be
suppressed globally via `tool.vulture.ignore_names` in pyproject.toml, not here.
"""

# 1. External dependencies
from mistletoe.block_token import Document

# 2. Domain Models
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.domain.models.planning_ports import SessionPorts

# 3. Ports & Services
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.web_scraper import WebScraper
from teddy_executor.core.ports.outbound.web_searcher import IWebSearcher
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner

# Reference all imports to satisfy Vulture and Mypy
_models = (
    Document,
    Plan,
    ActionData,
    SessionPorts,
    IEditSimulator,
    IPlanningUseCase,
    IRunPlanUseCase,
    IConfigService,
    IFileSystemManager,
    ILlmClient,
    IMarkdownReportFormatter,
    ISessionManager,
    IUserInteractor,
    WebScraper,
    IWebSearcher,
    SessionPlanner,
    SessionReplanner,
)

# Note: We must also alias specific methods that Vulture flags as unused,
# even if the parent class is heavily used in the system, because interfaces
# are often implemented but their methods aren't explicitly called in tests
# in a way Vulture can easily trace.
_methods = (
    IUserInteractor.confirm_plan_review,
    IUserInteractor.notify_skipped_action,
    IUserInteractor.ask_question,
    IFileSystemManager.create_file,
    IFileSystemManager.edit_file,
    ISessionManager.create_session,
)


# We include a dummy class to satisfy Textual UI event handler names
# that are not easily wildcarded in pyproject.toml.
class _TextualEventWhitelist:
    def compose(self) -> None:
        pass


_textual_dummy = _TextualEventWhitelist
