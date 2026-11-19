"""MRE: does malformed-plan correction feedback reach the LLM request?"""

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.services.planning_service import PlanningService
from teddy_executor.core.services.session_replanner import SessionReplanner

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


def build_service(llm: RecordingLlm) -> tuple[PlanningService, Mock, Mock]:
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
    prompts = Mock()
    prompts.resolve_message.side_effect = lambda message, _turn_path: message
    prompts.resolve_agent_metadata.return_value = (
        "developer",
        {"is_replan": True, "user_request": "Original human request"},
        "session/02/meta.yaml",
    )
    prompts.fetch_system_prompt.return_value = "system instructions"
    prompts.log_telemetry.return_value = 0.0
    fs = Mock()
    session_manager = Mock()
    session_manager.resolve_context_paths.return_value = {
        "Session": ["session/session.context"],
        "Turn": ["session/02/turn.context"],
    }
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
    return service, context, session_manager


def main() -> None:
    llm = RecordingLlm()
    service, context, _ = build_service(llm)
    replanner = SessionReplanner(Mock(), service)
    replanner.trigger_replan_turn(
        next_turn_dir="session/02",
        errors=[VALIDATION_ERROR],
        original_content=FAULTY_PLAN,
        validation_ast="# Faulty AST",
    )

    messages = llm.requests[-1]
    request_text = "\n".join(message["content"] for message in messages)
    context_file_args = context.get_context.call_args.kwargs["context_files"]

    print(f"roles: {[message['role'] for message in messages]}")
    print(f"context files resolved for the request: {context_file_args}")
    print(f"carries the validation error: {VALIDATION_ERROR in request_text}")
    print(f"carries the original faulty plan: {FAULTY_PLAN in request_text}")
    print(
        "carries the correction instruction: "
        f"{'failed validation' in request_text}"
    )
    print(f"final message starts with: {messages[-1]['content'][:60]!r}")

    missing = [
        label
        for label, present in (
            ("validation error", VALIDATION_ERROR in request_text),
            ("original faulty plan", FAULTY_PLAN in request_text),
            ("correction instruction", "failed validation" in request_text),
        )
        if not present
    ]
    if missing:
        print("\nMRE RESULT: replan request is missing " + ", ".join(missing))
        raise SystemExit(1)
    print("\nMRE RESULT: correction feedback reached the request.")


if __name__ == "__main__":
    main()
