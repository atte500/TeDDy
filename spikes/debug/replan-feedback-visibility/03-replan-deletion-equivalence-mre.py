"""MRE: deleting the discarded replan feedback changes nothing observable."""

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.services.planning_service import PlanningService
from teddy_executor.core.services.session_replanner import (
    SessionReplanner as ProductionReplanner,
)
from replica_session_replanner import SessionReplanner as ReplicaReplanner

VALIDATION_ERROR = (
    "Response must contain exactly one Level 1 heading and exactly one of "
    "## Action Plan or ## Message."
)
FAULTY_PLAN = "This malformed reply carries no heading at all."


class RecordingLlm:
    """Records every request; returns a valid plan-shaped response."""

    def __init__(self) -> None:
        self.requests: list[list[dict[str, str]]] = []

    def validate_config(self, include_remote: bool) -> list[str]:
        return []

    def get_text_token_count(self, text: str, model: str = "") -> int:
        return len(text)

    def get_token_count(self, messages: list[dict[str, str]]) -> int:
        return sum(len(message["content"]) for message in messages)

    def get_context_window(self, model: str = "") -> int:
        return 100_000

    def get_completion_cost(self, response: object, model_override: str) -> float:
        return 0.0

    def get_completion(
        self, messages: list[dict[str, str]], model: str
    ) -> SimpleNamespace:
        self.requests.append([dict(message) for message in messages])
        choice = SimpleNamespace(
            message=SimpleNamespace(content="# Corrected plan\n\n## Message\nDone."),
            finish_reason="stop",
        )
        return SimpleNamespace(model=model, choices=[choice])


def build_case(replanner_cls, invoke):
    llm = RecordingLlm()
    meta = {"is_replan": True, "user_request": "Original human request"}
    prompts = Mock()
    prompts.resolve_message.side_effect = lambda message, _turn_path: message
    prompts.resolve_agent_metadata.return_value = (
        "developer",
        meta,
        "session/02/meta.yaml",
    )
    prompts.fetch_system_prompt.return_value = "system instructions"
    prompts.log_telemetry.return_value = 0.0
    context = Mock()
    context.get_context.return_value = ProjectContext(
        header="# Project Context",
        content="## Session History\n### Turn 01: Report\nEarlier work.",
        scoped_paths={},
        git_status="",
    )
    config = Mock()
    config.get_setting.side_effect = lambda key, default=None: (
        "fake-model" if key == "llm.model" else default
    )
    session_manager = Mock()
    session_manager.resolve_context_paths.return_value = {
        "Session": ["session/session.context"],
        "Turn": ["session/02/turn.context"],
    }
    fs = Mock()
    service = PlanningService(
        PlanningPorts(
            context=context,
            llm=llm,
            fs=fs,
            config=config,
            prompts=prompts,
            ui=None,
            session_manager=session_manager,
        )
    )
    invoke(replanner_cls(fs, service))
    writes = {call.args[0]: call.args[1] for call in fs.write_file.call_args_list}
    return llm.requests[-1], writes, meta


def invoke_production(replanner) -> None:
    replanner.trigger_replan_turn(
        next_turn_dir="session/02",
        errors=[VALIDATION_ERROR],
        original_content=FAULTY_PLAN,
        validation_ast="# Faulty AST",
    )


def invoke_replica(replanner) -> None:
    replanner.trigger_replan_turn("session/02")


def main() -> None:
    prod_messages, prod_writes, prod_meta = build_case(
        ProductionReplanner, invoke_production
    )
    replica_messages, replica_writes, replica_meta = build_case(
        ReplicaReplanner, invoke_replica
    )

    checks = {
        "requests identical": prod_messages == replica_messages,
        "file writes identical": prod_writes == replica_writes,
        "turn metadata identical": prod_meta == replica_meta,
    }
    print(f"production roles: {[m['role'] for m in prod_messages]}")
    print(f"replica roles: {[m['role'] for m in replica_messages]}")
    for label, passed in checks.items():
        print(f"{label}: {passed}")
    print(
        "feedback text in production request: "
        f"{'failed validation' in str(prod_messages)}"
    )

    failed = [label for label, passed in checks.items() if not passed]
    if failed:
        print("\nMRE FAIL: " + ", ".join(failed))
        raise SystemExit(1)
    print("\nMRE PASS: deleting the feedback builder is behavior-preserving.")


if __name__ == "__main__":
    main()
