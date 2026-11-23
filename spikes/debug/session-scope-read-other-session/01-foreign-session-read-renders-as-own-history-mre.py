"""MRE: reading a file from another session renders it under the current
session's `## Session History` instead of `## Resource Contents`.

Run: uv run python spikes/debug/session-scope-read-other-session/01-foreign-session-read-renders-as-own-history-mre.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SPIKE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(SPIKE_DIR))

USE_REPLICA = "--replica" in sys.argv
USE_FIXED = "--fixed" in sys.argv
if USE_REPLICA:
    from replica_context_service import ContextService
else:
    from teddy_executor.core.services.context_service import ContextService


CURRENT_SESSION = ".teddy/sessions/20260521_100000-my-session"
FOREIGN_SESSION = ".teddy/sessions/20260521_120000-other-session"

OWN_INITIAL_REQUEST = f"{CURRENT_SESSION}/initial_request.md"
OWN_PLAN_1 = f"{CURRENT_SESSION}/01/plan.md"
OWN_REPORT_1 = f"{CURRENT_SESSION}/01/report.md"
FOREIGN_REPORT_3 = f"{FOREIGN_SESSION}/03/report.md"
WORKSPACE_FILE = "README.md"

FOREIGN_MARKER = "FOREIGN_SESSION_SENTINEL_CONTENT"
OWN_MARKER = "OWN_SESSION_SENTINEL_CONTENT"

FILE_CONTENTS = {
    OWN_INITIAL_REQUEST: "Implement the feature.",
    OWN_PLAN_1: "Plan for turn 1.",
    OWN_REPORT_1: f"# Own session report\n\n{OWN_MARKER}\n",
    FOREIGN_REPORT_3: f"# Other session report\n\n{FOREIGN_MARKER}\n",
    WORKSPACE_FILE: "# Readme\n",
}


class StubFileSystem:
    def is_dir(self, path: str) -> bool:
        return False

    def path_exists(self, path: str) -> bool:
        return path in FILE_CONTENTS

    def get_context_paths(self) -> list[str]:
        return []

    def read_files_in_vault(self, paths: list[str]) -> dict[str, str | None]:
        return {p: FILE_CONTENTS.get(p) for p in paths}


class StubTreeGenerator:
    max_depth = 3
    max_children = 20

    def generate_tree(self) -> str:
        return ""


class StubEnvironmentInspector:
    def get_environment_info(self) -> dict[str, str]:
        return {}

    def get_git_status(self) -> str:
        return ""


class StubLlmClient:
    def get_text_token_count(self, text: str, model: str | None = None) -> int:
        return 0


class StubWebScraper:
    def get_content(self, url: str, truncate: bool = True, **kwargs) -> str:
        return ""


def build_service() -> ContextService:
    return ContextService(
        file_system_manager=StubFileSystem(),
        repo_tree_generator=StubTreeGenerator(),
        environment_inspector=StubEnvironmentInspector(),
        llm_client=StubLlmClient(),
        web_scraper=StubWebScraper(),
        config_service=None,
    )


def locate_section(content: str, marker: str) -> str:
    idx = content.find(marker)
    if idx == -1:
        return "absent"
    history_idx = content.find("## Session History")
    resources_idx = content.find("## Resource Contents")
    if history_idx != -1 and idx > history_idx and (
        resources_idx == -1 or idx < resources_idx
    ):
        return "session_history"
    if resources_idx != -1 and idx > resources_idx:
        return "resource_contents"
    return "other"


def main() -> int:
    service = build_service()
    # A rooted caller knows which session it is rendering for; the unfixed
    # production run passes nothing and keeps the legacy partition.
    call_kwargs = {"session_root": CURRENT_SESSION} if USE_REPLICA or USE_FIXED else {}
    result = service.get_context(
        context_files={
            "Session": [
                OWN_INITIAL_REQUEST,
                OWN_PLAN_1,
                OWN_REPORT_1,
                WORKSPACE_FILE,
            ],
            "Turn": [FOREIGN_REPORT_3],
        },
        include_tokens=False,
        agent_name="Debugger",
        current_turn="01",
        **call_kwargs,
    )

    content = result.content
    foreign_section = locate_section(content, FOREIGN_MARKER)
    own_section = locate_section(content, OWN_MARKER)
    if USE_REPLICA:
        implementation = "replica"
    elif USE_FIXED:
        implementation = "fixed"
    else:
        implementation = "production"

    print("=== RENDERED CONTENT ===")
    print(content)
    print("=== END RENDERED CONTENT ===")
    print()
    print(f"Implementation: {implementation}")
    print(f"Foreign READ path: {FOREIGN_REPORT_3}")
    print(f"Foreign content rendered under: {foreign_section}")
    print(f"Own history content rendered under: {own_section}")
    print()

    if own_section != "session_history":
        print("VERDICT: UNEXPECTED - own history is not under ## Session History")
        return 2
    if foreign_section == "session_history":
        print("VERDICT: BUG REPRODUCED - foreign READ lands in ## Session History")
        return 1
    if foreign_section == "resource_contents":
        print("VERDICT: OK - foreign READ lands in ## Resource Contents")
        return 0
    print(f"VERDICT: UNEXPECTED - foreign content section: {foreign_section}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
