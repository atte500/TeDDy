"""Integration: the LLM context window caps plan.md at plan.max_lines.

Truncate-first: the plan content embedded in the payload AND the plan's
ContextItem.token_count both reflect the capped length, so pruning budgets
track real window impact. The on-disk plan.md always stays full. Only
plan.md is capped; other files embed verbatim.
"""

from pathlib import Path

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper
from teddy_executor.core.services.context_service import ContextService
from teddy_executor.core.services.edit_simulator import EditSimulator
from tests.harness.setup.mocking import register_mock

PLAN_REL = "docs/turns/01/plan.md"
REPORT_REL = "docs/turns/01/report.md"


def _build_service(
    container, root: Path, max_lines: int
) -> tuple[ContextService, object]:
    """Assemble a ContextService over the real filesystem and injected fakes."""
    file_system = LocalFileSystemAdapter(
        edit_simulator=EditSimulator(), root_dir=str(root)
    )
    config = register_mock(container, IConfigService)
    config.get_setting.side_effect = lambda key, default=None: (
        max_lines if key == "plan.max_lines" else default
    )
    llm = register_mock(container, ILlmClient)
    llm.get_text_token_count.side_effect = lambda text: len(text.split())
    tree = register_mock(container, IRepoTreeGenerator)
    tree.generate_tree.return_value = ""
    tree.max_depth = 3
    tree.max_children = 20
    env = register_mock(container, IEnvironmentInspector)
    env.get_environment_info.return_value = {}
    env.get_git_status.return_value = None
    scraper = register_mock(container, IWebScraper)

    service = ContextService(
        file_system_manager=file_system,
        repo_tree_generator=tree,
        environment_inspector=env,
        llm_client=llm,
        web_scraper=scraper,
        config_service=config,
    )
    return service, llm


def _write(root: Path, rel: str, line_count: int) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"line {i}" for i in range(1, line_count + 1))
    target.write_text(body + "\n", encoding="utf-8")


def test_plan_content_is_capped_in_context_and_disk_stays_full(container, tmp_path):
    _write(tmp_path, PLAN_REL, 500)
    service, _ = _build_service(container, tmp_path, 200)

    context = service.get_context(context_files={"Turn": [PLAN_REL]})

    assert "line 200" in context.content
    assert "line 201" not in context.content
    assert "[Showing first 200 of 500 lines.]" in context.content

    disk = (tmp_path / PLAN_REL).read_text(encoding="utf-8")
    assert "line 500" in disk


def test_plan_item_token_count_reflects_capped_content(container, tmp_path):
    _write(tmp_path, PLAN_REL, 500)
    service, _ = _build_service(container, tmp_path, 200)

    context = service.get_context(context_files={"Turn": [PLAN_REL]})

    item = next(i for i in context.items if i.path == PLAN_REL)
    full_tokens = len(" ".join(f"line {i}" for i in range(1, 501)).split())
    assert 0 < item.token_count < full_tokens


def test_non_plan_file_is_not_capped(container, tmp_path):
    _write(tmp_path, REPORT_REL, 500)
    service, _ = _build_service(container, tmp_path, 200)

    context = service.get_context(context_files={"Turn": [REPORT_REL]})

    assert "line 500" in context.content
    assert "[Showing first 200 of 500 lines.]" not in context.content
