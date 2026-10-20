"""Attribute the full warm header-to-telemetry window on the live session.

Mirrors `PlanningService.generate_plan` from the header print to the
telemetry block on a warm process, so every cost that a later session turn
pays is measured in one sequence. Context assembly runs twice, once with
`include_tokens=False`, to isolate per-file tokenization from the file reads
and the repository tree walk.
"""

import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path("src").resolve()))

import litellm  # noqa: F401  # simulate the CLI prewarm so timings are warm

from teddy_executor.container import create_container
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import ILlmClient, ISessionManager
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


def run_window(turn: Path) -> None:
    """Time the warm pre-LLM window in execution order."""
    meta = yaml.safe_load((turn / "meta.yaml").read_text(encoding="utf-8"))
    agent = str(meta.get("agent_name") or "Pathfinder")
    model = str(meta.get("model") or "")
    session = turn.parent

    total_start = time.perf_counter()

    container = create_container()
    llm = container.resolve(ILlmClient)
    context_service = container.resolve(IGetContextUseCase)
    session_manager = container.resolve(ISessionManager)
    prompt_manager = container.resolve(IPromptManager)

    timed(
        "validate_config (preflight)",
        lambda: llm.validate_config(include_remote=False),
    )
    resolved = timed(
        "resolve_context_paths",
        lambda: session_manager.resolve_context_paths((turn / "plan.md").as_posix()),
    )
    system_prompt = timed(
        "fetch_system_prompt",
        lambda: prompt_manager.fetch_system_prompt(agent, turn),
    )
    timed(
        "system get_text_token_count",
        lambda: llm.get_text_token_count(system_prompt, model=model),
    )
    timed(
        "get_context (include_tokens=False)",
        lambda: context_service.get_context(
            context_files=resolved,
            include_tokens=False,
            agent_name=agent,
            current_turn=turn.name,
            cache_dir=str(session),
        ),
    )
    context = timed(
        "get_context (include_tokens=True)",
        lambda: context_service.get_context(
            context_files=resolved,
            agent_name=agent,
            current_turn=turn.name,
            system_prompt_tokens=0,
            cache_dir=str(session),
        ),
    )

    full_context = f"{context.header}\n{context.content}"
    print("payload bytes", len(full_context.encode("utf-8")))
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": full_context},
    ]
    timed("get_token_count (messages)", lambda: llm.get_token_count(messages=messages))
    timed("get_context_window", lambda: llm.get_context_window(model=model))
    timed("supports_pricing", lambda: llm.supports_pricing(model=model))
    print(f"TOTAL window: {time.perf_counter() - total_start:.3f}s")


def main() -> None:
    turn = latest_turn()
    print("turn", turn.name, "session", turn.parent.name)
    for index in (1, 2):
        print(f"== run {index} ==")
        run_window(turn)


if __name__ == "__main__":
    main()