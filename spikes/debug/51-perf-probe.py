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
import shutil
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
LLM = None
PROMPT_MANAGER = None
SESSION_MANAGER = None
TURN_DIR = None
AGENT_NAME = None
META = None
SYSTEM_PROMPT = None
CTX_FILES = None
FULL_CONTEXT = None


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


def stage_which_precommit():
    shutil.which("pre-commit")


def stage_precommit_install():
    # Mirrors _ensure_commit_hooks() in session_cli_handlers.py, executed on
    # EVERY `teddy start`. Full Python interpreter + pre-commit framework.
    subprocess.run(
        ["pre-commit", "install", "-f", "-t", "pre-commit", "-t", "post-commit"],
        capture_output=True,
        check=True,
        cwd=str(REPO_ROOT),
    )


def stage_which_git():
    shutil.which("git")


def stage_resolve_llm():
    global LLM
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient

    LLM = CONTAINER.resolve(ILlmClient)


def stage_validate_config():
    # Mirrors _run_cli_preflight_check (local-only validation).
    LLM.validate_config(include_remote=False)


def stage_prompt_lookup():
    from teddy_executor.prompts import find_prompt_content

    find_prompt_content("pathfinder")


def stage_resolve_prompt_manager():
    global PROMPT_MANAGER
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

    PROMPT_MANAGER = CONTAINER.resolve(IPromptManager)


def stage_resolve_session_manager():
    global SESSION_MANAGER
    from teddy_executor.core.ports.outbound.session_manager import ISessionManager

    SESSION_MANAGER = CONTAINER.resolve(ISessionManager)


def stage_fixture_create():
    """Create a minimal session/turn fixture in a temp dir (mirrors create_session output)."""
    global TURN_DIR
    import tempfile

    base = Path(tempfile.mkdtemp(prefix="teddy-probe-"))
    session_dir = base / "20260101_000000-probe"
    TURN_DIR = session_dir / "01"
    TURN_DIR.mkdir(parents=True)
    (TURN_DIR / "meta.yaml").write_text(
        "agent_name: pathfinder\nmodel: openrouter/openai/gpt-4o-mini\n",
        encoding="utf-8",
    )
    (TURN_DIR / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (TURN_DIR / "turn.context").write_text("README.md\n", encoding="utf-8")
    (session_dir / "session.context").write_text("README.md\n", encoding="utf-8")


def stage_resolve_agent_metadata():
    global AGENT_NAME, META
    AGENT_NAME, META, _meta_path = PROMPT_MANAGER.resolve_agent_metadata(TURN_DIR)


def stage_fetch_system_prompt():
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = PROMPT_MANAGER.fetch_system_prompt(AGENT_NAME, TURN_DIR)


def stage_system_token_count():
    # PlanningService counts the system prompt EVERY turn before building context.
    LLM.get_text_token_count(SYSTEM_PROMPT, model=str(META.get("model") or ""))


def stage_resolve_context_paths():
    global CTX_FILES
    CTX_FILES = SESSION_MANAGER.resolve_context_paths(str(TURN_DIR / "plan.md"))


def stage_planning_get_context():
    # The full context assembly that precedes every input.md write.
    global FULL_CONTEXT
    ctx = CONTEXT_SERVICE.get_context(
        context_files=CTX_FILES,
        agent_name=AGENT_NAME,
        current_turn=TURN_DIR.name,
        system_prompt_tokens=0,
        cache_dir=str(TURN_DIR.parent),
    )
    FULL_CONTEXT = f"{ctx.header}\n{ctx.content}"


def stage_write_input_md():
    (TURN_DIR / "input.md").write_text(FULL_CONTEXT, encoding="utf-8")


def stage_get_context_window():
    LLM.get_context_window()


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

    # PASS 3: startup bootstrap (handle_new_session health checks) +
    # planning pre-LLM pipeline (the per-turn input.md assembly path).
    timed("which-pre-commit", stage_which_precommit)
    timed("pre-commit-install", stage_precommit_install)
    timed("which-git", stage_which_git)
    timed("resolve-llm", stage_resolve_llm)
    timed("validate-config-local", stage_validate_config)
    timed("prompt-lookup", stage_prompt_lookup)
    timed("resolve-prompt-manager", stage_resolve_prompt_manager)
    timed("resolve-session-manager", stage_resolve_session_manager)
    timed("fixture-create", stage_fixture_create)
    timed("resolve-agent-metadata", stage_resolve_agent_metadata)
    timed("fetch-system-prompt", stage_fetch_system_prompt)
    timed("system-token-count", stage_system_token_count)
    timed("resolve-context-paths", stage_resolve_context_paths)
    timed("planning-get-context", stage_planning_get_context)
    timed("write-input-md", stage_write_input_md)
    timed("get-context-window", stage_get_context_window)
    report("PASS 3 (bootstrap + planning pre-LLM pipeline)")


if __name__ == "__main__":
    main()