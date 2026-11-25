"""MRE: a PDF path in the turn context crashes the next context assembly.

Reported failure: turn [02] READ a local PDF successfully (the extractor path),
the path then landed in the following turn's context, and assembling that
payload died with "'utf-8' codec can't decode byte 0xe2 in position 10".

The MRE feeds the PDF path into the turn scope only, so every incidental
argument drops away: no URLs, no LLM token counting, no git status.

Run from the project root:
    uv run python spikes/debug/pdf-context-utf8-decode/01-pdf-context-embed-crash-mre.py

By default the MRE writes its own minimal one-page PDF to `.tmp/debug/`, so the
reproduction needs no external download: that fixture carries the same
`%PDF-1.x\r%` header, which places the binary comment marker at byte 10 and
makes a naive UTF-8 decode fail at exactly `position 10`.

Environment:
    MRE_CONTEXT_SERVICE_MODULE  Module to import ContextService from. Defaults
                                to the production module. Set it to
                                `replica_context_service` to exercise the fix.
    MRE_PDF_PATH                Project-root-relative PDF to embed instead of
                                the generated fixture.

Exit codes: 0 = context assembled, 1 = UnicodeDecodeError, 2 = setup problem.
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Any

SPIKE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SPIKE_DIR.parents[2]
for _entry in (str(PROJECT_ROOT), str(SPIKE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from teddy_executor.adapters.outbound.local_file_system_adapter import (  # noqa: E402
    LocalFileSystemAdapter,
)
from teddy_executor.adapters.outbound.pypdf_extractor import PypdfExtractor  # noqa: E402
from teddy_executor.core.services.edit_simulator import EditSimulator  # noqa: E402
from fixture_pdf import build_fixture_pdf  # noqa: E402

TURN = "03"


class _RepoTreeStub:
    """Stand-in for the tree generator; the tree itself is incidental."""

    max_depth = 1
    max_children = 1

    def generate_tree(self) -> str:
        return "."


class _EnvironmentStub:
    """Stand-in for the host inspector; identity rows are incidental."""

    def get_environment_info(self) -> dict[str, str]:
        return {
            "cwd": str(PROJECT_ROOT),
            "os_name": "MRE",
            "os_version": "",
            "shell": "zsh",
        }

    def get_git_status(self) -> str:
        return ""


class _LlmStub:
    """Stand-in for token counting; the MRE runs with include_tokens=False."""

    def get_text_token_count(self, text: str, model: str | None = None) -> int:
        return len(text)


class _WebScraperStub:
    """Stand-in for remote fetches; the MRE never passes a URL."""

    def get_content(self, url: str, truncate: bool = True) -> str:
        raise AssertionError(f"MRE must not fetch a URL, got {url}")


def _build_service(context_service_class: Any) -> Any:
    """Assemble the service with real filesystem pieces and injected stubs."""
    ports: dict[str, Any] = {
        "file_system_manager": LocalFileSystemAdapter(
            edit_simulator=EditSimulator(), root_dir=str(PROJECT_ROOT)
        ),
        "repo_tree_generator": _RepoTreeStub(),
        "environment_inspector": _EnvironmentStub(),
        "llm_client": _LlmStub(),
        "web_scraper": _WebScraperStub(),
    }
    accepted = inspect.signature(context_service_class.__init__).parameters
    if "pdf_extractor" in accepted:
        ports["pdf_extractor"] = PypdfExtractor()
    return context_service_class(**ports)


def _load_context_service_module() -> Any:
    """Import the service under test: production by default, replica on demand."""
    module_name = os.environ.get(
        "MRE_CONTEXT_SERVICE_MODULE", "teddy_executor.core.services.context_service"
    )
    return importlib.import_module(module_name)


def main() -> int:
    pdf_path = os.environ.get("MRE_PDF_PATH") or build_fixture_pdf()
    if not (PROJECT_ROOT / pdf_path).exists():
        print(f"MRE SETUP: {pdf_path} is missing from the project root")
        return 2

    module = _load_context_service_module()
    print(f"ContextService from: {Path(inspect.getfile(module)).name}")

    service = _build_service(module.ContextService)
    try:
        context = service.get_context(
            context_files={"Turn": [pdf_path]},
            include_tokens=False,
            current_turn=TURN,
        )
    except UnicodeDecodeError as error:
        print(f"REPRODUCED: {error}")
        return 1

    embedded = context.content
    heading_at = embedded.find(pdf_path)
    print("NO CRASH: the turn context assembled")
    print(f"payload characters: {len(embedded)}")
    print(f"renders FILE NOT FOUND marker: {'FILE NOT FOUND' in embedded}")
    print("--- resource excerpt ---")
    print(embedded[max(heading_at - 20, 0):heading_at + 320])
    return 0


if __name__ == "__main__":
    sys.exit(main())
