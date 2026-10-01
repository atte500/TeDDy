"""Case File 51: Windows-vs-macOS comparative performance probe.

Measures stage-level timings for the two slow paths reported:
  1. CLI startup (imports, container init, end-to-end cold CLI invocation)
  2. Per-turn context assembly (ContextService.get_context)

Runs identically on macOS (local baseline) and Windows (CI remote probe),
printing one "STAGE <name>: <seconds>s (<status>)" line per measurement
so results can be diffed across platforms.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT / "src"))

RESULTS: list[tuple[str, float, str]] = []
CONTAINER = None
CONTEXT_SERVICE = None
TREE = None


def timed(name, fn):
    """Run fn(), recording wall-clock duration and success/failure."""
    t0 = time.perf_counter()
    try:
        fn()
        status = "ok"
    except Exception as exc:  # diagnostic probe must not die mid-run
        status = "FAIL {}: {}".format(type(exc).__name__, exc)
    dt = time.perf_counter() - t0
    RESULTS.append((name, dt, status))


def report(label):
    print("\n=== {} ===".format(label))
    for name, dt, status in RESULTS:
        print("STAGE {}: {:.4f}s ({})".format(name, dt, status))
    RESULTS.clear()


def stage_import_typer():
    import typer  # noqa: F401


def stage_import_container_module():
    import teddy_executor.container  # noqa: F401


def stage_get_container():
    global CONTAINER
    from teddy_executor.container import get_container

    CONTAINER = get_container()


def stage_ensure_initialized():
    from teddy_executor.__main__ import _ensure_project_initialized

    _ensure_project_initialized(CONTAINER)


def stage_resolve_context_service():
    global CONTEXT_SERVICE
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )

    CONTEXT_SERVICE = CONTAINER.resolve(IGetContextUseCase)


def stage_env_info():
    CONTEXT_SERVICE._environment_inspector.get_environment_info()


def stage_git_status_short():
    CONTEXT_SERVICE._environment_inspector.get_git_status()


def stage_git_status_full():
    CONTEXT_SERVICE._environment_inspector.get_full_git_status()


def stage_tree_generator_init():
    global TREE
    from teddy_executor.adapters.outbound.local_repo_tree_generator import (
        LocalRepoTreeGenerator,
    )

    TREE = LocalRepoTreeGenerator(str(REPO_ROOT))


def stage_tree_generate():
    TREE.generate_tree()


def stage_subprocess_git_version():
    subprocess.run(["git", "--version"], capture_output=True, check=True)


def stage_subprocess_python_child():
    subprocess.run([sys.executable, "-c", "pass"], capture_output=True, check=True)


def stage_token_count_cold():
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient

    llm = CONTAINER.resolve(ILlmClient)
    llm.get_text_token_count("hello world this is a token counting probe")


def stage_token_count_large_warm():
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient

    llm = CONTAINER.resolve(ILlmClient)
    llm.get_text_token_count("word " * 20000)


def stage_get_context_no_tokens():
    CONTEXT_SERVICE.get_context(include_tokens=False)


def stage_get_context_with_tokens():
    # Models the real per-turn path: session_orchestrator calls get_context
    # without include_tokens, so token counting IS performed every turn.
    CONTEXT_SERVICE.get_context(include_tokens=True)


def stage_cli_end_to_end_version():
    # Full cold CLI startup proxy (interpreter + typer + container init).
    subprocess.run(
        [sys.executable, "-m", "teddy_executor", "--version"],
        capture_output=True,
        check=True,
        cwd=str(REPO_ROOT),
    )


def main():
    print("platform: {} | python: {}".format(sys.platform, sys.version.split()[0]))

    # PASS 1 (cold): one-time costs
    timed("import-typer", stage_import_typer)
    timed("import-container-module", stage_import_container_module)
    timed("get-container", stage_get_container)
    timed("ensure-project-initialized", stage_ensure_initialized)
    timed("resolve-context-service", stage_resolve_context_service)
    timed("subprocess-git-version", stage_subprocess_git_version)
    timed("subprocess-python-child", stage_subprocess_python_child)
    timed("env-inspector-info", stage_env_info)
    timed("git-status-short", stage_git_status_short)
    timed("git-status-full", stage_git_status_full)
    timed("tree-generator-init", stage_tree_generator_init)
    timed("tree-generate", stage_tree_generate)
    timed("get-context-no-tokens", stage_get_context_no_tokens)
    timed("token-count-cold", stage_token_count_cold)
    timed("token-count-large-warm", stage_token_count_large_warm)
    timed("get-context-with-tokens", stage_get_context_with_tokens)
    timed("cli-end-to-end-version", stage_cli_end_to_end_version)
    report("PASS 1 (cold)")

    # PASS 2 (warm): steady-state per-turn cost (imports already cached)
    timed("git-status-short", stage_git_status_short)
    timed("git-status-full", stage_git_status_full)
    timed("tree-generate", stage_tree_generate)
    timed("get-context-no-tokens", stage_get_context_no_tokens)
    timed("get-context-with-tokens", stage_get_context_with_tokens)
    report("PASS 2 (warm / per-turn steady state)")


if __name__ == "__main__":
    main()