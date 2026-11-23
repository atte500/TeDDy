"""Unit coverage: ContextService threads the effective model into token counts.

A session running a persona model must count tokens with that model, because a
different model can use a different tokenizer. The effective model is threaded
from the caller down to every ``get_text_token_count`` call.
"""

from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper
from teddy_executor.core.services.context_service import ContextService


def _build_service():
    """Construct a ContextService over spec-bound, in-memory doubles."""
    fs = POSIXPathMock(spec=IFileSystemManager)
    fs.get_context_paths.return_value = []
    fs.read_files_in_vault.return_value = {}

    tree = POSIXPathMock(spec=IRepoTreeGenerator)
    tree.generate_tree.return_value = ""
    tree.max_depth = 3
    tree.max_children = 20

    inspector = POSIXPathMock(spec=IEnvironmentInspector)
    inspector.get_environment_info.return_value = {}
    inspector.get_git_status.return_value = None

    llm = POSIXPathMock(spec=ILlmClient)
    llm.get_text_token_count.return_value = 5

    scraper = POSIXPathMock(spec=IWebScraper)

    config = POSIXPathMock(spec=IConfigService)
    config.get_setting.side_effect = lambda key, default=None: default

    return ContextService(fs, tree, inspector, llm, scraper, config), llm


def test_get_context_threads_the_model_to_token_count():
    """The caller's effective model reaches every token-count call."""
    service, llm = _build_service()

    service.get_context(include_tokens=True, model="persona/model")

    llm.get_text_token_count.assert_called_once()
    assert llm.get_text_token_count.call_args.kwargs.get("model") == "persona/model"
