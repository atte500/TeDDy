"""MRE: plan.max_lines is ignored by the production context service.

Builds the real composition root in a temp workspace whose
.teddy/config.yaml sets plan.max_lines: 5, then checks whether the
embedded plan.md is head-truncated. Pass ``replica`` to load the
sandbox copy of the composition root instead of the production module.
"""

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

CAP = 5
PLAN_LINES = 10
MARKER = f"[Showing first {CAP} of {PLAN_LINES} lines.]"


def load_container_module(impl: str):
    """Return a module exposing ``create_container`` for the chosen impl."""
    if impl == "production":
        from teddy_executor import container

        return container
    replica_path = Path(__file__).resolve().parent / "replica_container.py"
    spec = importlib.util.spec_from_file_location("replica_container_mre", replica_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load replica at {replica_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_workspace() -> Path:
    """Create a temp workspace with a 10-line plan and a 5-line cap."""
    root = Path(tempfile.mkdtemp(prefix="teddy-mre-"))
    (root / ".teddy").mkdir()
    (root / ".teddy" / "config.yaml").write_text(
        f"plan:\n  max_lines: {CAP}\n", encoding="utf-8"
    )
    body = "\n".join(f"line {i}" for i in range(1, PLAN_LINES + 1))
    (root / "plan.md").write_text(body + "\n", encoding="utf-8")
    return root


def main() -> int:
    impl = sys.argv[1] if len(sys.argv) > 1 else "production"
    workspace = build_workspace()
    previous_cwd = os.getcwd()
    os.chdir(workspace)
    try:
        from teddy_executor.core.ports.inbound.get_context_use_case import (
            IGetContextUseCase,
        )
        from teddy_executor.core.ports.outbound.config_service import IConfigService

        module = load_container_module(impl)
        container = module.create_container()
        config = container.resolve(IConfigService)
        service = container.resolve(IGetContextUseCase)
        context = service.get_context(
            context_files={"Turn": ["plan.md"]}, include_tokens=False
        )
    finally:
        os.chdir(previous_cwd)

    adapter_cap = config.get_setting("plan.max_lines", "MISSING")
    effective_cap = service._resolve_plan_max_lines()
    has_config = service._config_service is not None
    marker_present = MARKER in context.content
    tail_present = f"line {PLAN_LINES}" in context.content

    print(f"impl                  -> {impl}")
    print(f"adapter plan cap      -> {adapter_cap}")
    print(f"service has config    -> {has_config}")
    print(f"effective plan cap    -> {effective_cap}")
    print(f"truncation marker     -> {marker_present}")
    print(f"tail line {PLAN_LINES} embedded -> {tail_present}")

    truncated = marker_present and not tail_present
    print(f"RESULT                -> {'TRUNCATED' if truncated else 'NOT TRUNCATED'}")
    return 0 if truncated else 1


if __name__ == "__main__":
    sys.exit(main())
