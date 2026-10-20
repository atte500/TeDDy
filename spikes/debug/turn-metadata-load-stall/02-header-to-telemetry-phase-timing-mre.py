"""Time each phase between the turn header print and the telemetry block.

Uses the real composition root and the live turn's context files, so the
measured phases match `PlanningService.generate_plan` in execution order. The
input payload is written to the system temp directory, never to session state.
"""

import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path("src").resolve()))

from teddy_executor.container import create_container
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import (
    IConfigService,
    IEnvironmentInspector,
    ILlmClient,
    IRepoTreeGenerator,
    ISessionManager,
)
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager


def timed(label: str, function):
    """Run a callable, print its wall-clock cost, and return its result."""
    start = time.perf_counter()
    result = function()
    print(f"{label}: {time.perf_counter() - start:.3f}s")
    return result


def latest_turn() -> Path:
    """Resolve the newest session and its highest-numbered turn directory."""
    sessions = sorted(
        [p for p in Path(".teddy/sessions").iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
    )
    session = sessions[-1]
    turns = sorted(
        [p for p in session.iterdir() if p.is_dir() and p.name.isdigit()],
        key=lambda p: p.name,
    )
    return turns[-1]


def main() -> None:
    turn = latest_turn()
    session = turn.parent
    meta = yaml.safe_load((turn / "meta.yaml").read_text(encoding="utf-8"))
    model = str(meta.get("model") or "")

    container = create_container()
    config = container.resolve(IConfigService)
    llm = container.resolve(ILlmClient)
    context_service = container.resolve(IGetContextUseCase)
    session_manager = container.resolve(ISessionManager)
    tree_generator = container.resolve(IRepoTreeGenerator)
    inspector = container.resolve(IEnvironmentInspector)
    prompt_manager = container.resolve(IPromptManager)

    print("== preflight ==")
    timed("validate_config", lambda: llm.validate_config(include_remote=False))

    print("== context inputs ==")
    resolved = timed(
        "resolve_context_paths",
        lambda: session_manager.resolve_context_paths((turn / "plan.md").as_posix()),
    )
    timed("git_status", lambda: inspector.get_git_status())
    timed("repo_tree", lambda: tree_generator.generate_tree())

    print("== context assembly ==")
    context = timed(
        "get_context",
        lambda: context_service.get_context(
            context_files=resolved,
            agent_name="Debugger",
            current_turn=turn.name,
            system_prompt_tokens=0,
            cache_dir=str(session),
        ),
    )

    print("== prompt and token counting ==")
    system_prompt = timed(
        "fetch_system_prompt",
        lambda: prompt_manager.fetch_system_prompt("Debugger", turn),
    )
    timed(
        "system get_text_token_count",
        lambda: llm.get_text_token_count(system_prompt, model=model),
    )
    full_context = f"{context.header}\n{context.content}"
    probe_path = Path(tempfile.gettempdir()) / "teddy-probe-input.md"
    timed("write input.md (temp)", lambda: probe_path.write_text(full_context, encoding="utf-8"))
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": full_context},
    ]
    timed("get_token_count", lambda: llm.get_token_count(messages=messages))

    print("== telemetry calls ==")
    timed("get_context_window #1", lambda: llm.get_context_window(model=model))
    timed("get_context_window #2", lambda: llm.get_context_window(model=model))
    timed("supports_pricing", lambda: llm.supports_pricing(model=model))


if __name__ == "__main__":
    main()