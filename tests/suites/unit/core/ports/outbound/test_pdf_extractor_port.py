from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.ports.outbound import IFileSystemManager, IPdfExtractor


class _FakePdfExtractor:
    def extract_text(self, data: bytes, source: str) -> str:
        return f"text from {source}"


class _MissingExtractText:
    pass


def test_object_with_extract_text_satisfies_the_port():
    assert isinstance(_FakePdfExtractor(), IPdfExtractor)


def test_object_without_extract_text_does_not_satisfy_the_port():
    assert not isinstance(_MissingExtractText(), IPdfExtractor)


def test_file_system_port_declares_binary_read():
    assert callable(getattr(IFileSystemManager, "read_file_bytes", None))


def _build_ports(**overrides):
    placeholder = object()
    fields = {
        "shell_executor": placeholder,
        "file_system_manager": placeholder,
        "user_interactor": placeholder,
        "web_scraper": placeholder,
        "web_searcher": placeholder,
    }
    fields.update(overrides)
    return ActionPorts(**fields)


def test_action_ports_defaults_pdf_extractor_to_none():
    assert _build_ports().pdf_extractor is None


def test_action_ports_accepts_an_injected_pdf_extractor():
    extractor = _FakePdfExtractor()

    assert _build_ports(pdf_extractor=extractor).pdf_extractor is extractor
