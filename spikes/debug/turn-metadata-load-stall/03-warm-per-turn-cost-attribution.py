"""Attribute the header-to-telemetry stall to cold import or per-turn work.

Probe 02 measured the very first ``validate_config`` call at 2.5s, but that
call also paid the one-time LiteLLM import. A live session's later turns reuse
the already imported module, so this probe separates the cold-import cost from
the warm per-turn cost of validation, context assembly, tree generation, and
the git shell-out.
"""

import importlib.metadata as metadata
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path("src").resolve()))


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
    meta = yaml.safe_load((turn / "meta.yaml").read_text(encoding="utf-8"))
    model = str(meta.get("model") or "")

    print("== cold import (paid once per process) ==")
    litellm = timed("cold import litellm", lambda: __import__("litellm"))
    print("litellm", metadata.version("litellm"))
    print("model", model)

    print("== warm validate_environment (what later turns pay) ==")
    for index in range(3):
        timed(
            f"litellm.validate_environment #{index + 1}",
            lambda: litellm.validate_environment(model=model),
        )

    print("== warm validate_config on a fresh adapter each call ==")
    from teddy_executor.container import create_container
    from teddy_executor.core.ports.outbound import ILlmClient

    for index in range(3):
        adapter = create_container().resolve(ILlmClient)
        timed(
            f"validate_config (fresh adapter) #{index + 1}",
            lambda a=adapter: a.validate_config(include_remote=False),
        )

    print("== warm context cost, repeated ==")
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )
    from teddy_executor.core.ports.outbound import (
        IEnvironmentInspector,
        IRepoTreeGenerator,
        ISessionManager,
    )

    container = create_container()
    context_service = container.resolve(IGetContextUseCase)
    session_manager = container.resolve(ISessionManager)
    tree_generator = container.resolve(IRepoTreeGenerator)
    inspector = container.resolve(IEnvironmentInspector)
    resolved = session_manager.resolve_context_paths((turn / "plan.md").as_posix())

    for index in range(3):
        timed(f"repo_tree #{index + 1}", lambda: tree_generator.generate_tree())
        timed(f"git_status #{index + 1}", lambda: inspector.get_git_status())
    for index in range(2):
        timed(
            f"get_context #{index + 1}",
            lambda: context_service.get_context(
                context_files=resolved,
                agent_name="Debugger",
                current_turn=turn.name,
                system_prompt_tokens=0,
                cache_dir=str(turn.parent),
            ),
        )


if __name__ == "__main__":
    main()