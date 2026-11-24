from teddy_executor.adapters.outbound.pypdf_extractor import PypdfExtractor
from teddy_executor.container import create_container
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import IPdfExtractor, IWebScraper
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy_executor.core.services.action_dispatcher import IActionFactory
from teddy_executor.core.services.context_service import ContextService
from tests.harness.setup.mocking import POSIXPathMock
from tests.harness.setup.pdf_fixture import build_minimal_pdf


def test_container_resolves_foundational_services(container):
    """
    Integration test ensuring the DI container correctly resolves foundational
    outbound ports.
    """
    # Act
    config_service = container.resolve(IConfigService)
    llm_client = container.resolve(ILlmClient)

    # Assert
    assert config_service is not None
    assert llm_client is not None
    # We assert on the interface/port type since the implementation might be
    # a mock depending on the fixture's configuration.
    assert isinstance(config_service, IConfigService)
    assert isinstance(llm_client, ILlmClient)


def test_tree_generator_receives_configured_max_depth(container):
    """The composition root injects context.max_depth into the factory."""
    config_service = container.resolve(IConfigService)
    expected_depth = config_service.get_setting("context.max_depth", 0)

    generator = container.resolve(IRepoTreeGenerator)

    assert generator._max_depth == expected_depth


def test_context_use_case_receives_the_injected_config_service(container):
    """The inbound context port must inherit the composition root's config service.

    Regression: registering the bare ContextService class for the port made punq
    auto-resolve the constructor and substitute config_service=None, so
    plan.max_lines silently fell back to the schema default.
    """
    context_service = container.resolve(IGetContextUseCase)

    assert isinstance(context_service, ContextService)
    assert isinstance(context_service._config_service, IConfigService)


def test_composition_root_caps_plan_content_at_plan_max_lines(monkeypatch, tmp_path):
    """The container-built context service honours the configured plan cap."""
    (tmp_path / ".teddy").mkdir()
    (tmp_path / ".teddy" / "config.yaml").write_text(
        "plan:\n  max_lines: 5\n", encoding="utf-8"
    )
    plan = "\n".join(f"line {i}" for i in range(1, 11))
    (tmp_path / "plan.md").write_text(plan + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    context_service = create_container().resolve(IGetContextUseCase)
    context = context_service.get_context(
        context_files={"Turn": ["plan.md"]}, include_tokens=False
    )

    assert "[Showing first 5 of 10 lines.]" in context.content
    assert "line 10" not in context.content


def test_container_registers_the_pypdf_extractor():
    """The composition root resolves the real PDF extractor adapter."""
    extractor = create_container().resolve(IPdfExtractor)

    assert isinstance(extractor, PypdfExtractor)


def test_resolved_scraper_extracts_text_from_a_pdf_url():
    """The resolved scraper carries the injected extractor into its PDF branch."""
    scraper = create_container().resolve(IWebScraper)
    scraper._fetch_pdf_bytes = POSIXPathMock(
        return_value=build_minimal_pdf("Hello PDF")
    )

    result = scraper.get_content("https://example.com/report.pdf")

    assert "Hello PDF" in result


def test_composition_root_reads_a_local_pdf(monkeypatch, tmp_path):
    """The resolved factory reads a real PDF from disk through the whole stack."""
    (tmp_path / "report.pdf").write_bytes(build_minimal_pdf("Quarterly Report"))
    monkeypatch.chdir(tmp_path)

    factory = create_container().resolve(IActionFactory)
    action = factory.create_action(
        "READ", {"resource": "report.pdf", "path": "report.pdf"}
    )

    assert "Quarterly Report" in action.execute(path="report.pdf")
