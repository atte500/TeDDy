import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

# Ensure we can import from src
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from teddy_executor.core.domain.models import ProjectContext, ContextItem, Plan
from teddy_executor.core.domain.models.plan import ActionData, ActionType
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import CONTEXT_ROOT

def setup_showcase_data():
    """Sets up the mocks and mock context data."""
    mock_config = MagicMock(spec=IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 10000,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.max_turns_retention": 5,
    }.get(key, default)

    mock_fs = MagicMock(spec=IFileSystemManager)
    mock_fs.path_exists.return_value = True

    def mock_read(path):
        if "01/plan.md" in path: return "- **Status:** 🔴 Failure"
        if "02/plan.md" in path: return "- **Status:** 🟢 Success"
        if "06/plan.md" in path: return "- **Status:** 🔴"
        if "07/plan.md" in path: return "- **Status:** 🟢"
        if "10/report.md" in path: return "- **Overall Status:** Validation Failed"
        if "11/plan.md" in path: return "- **Status:** 🔴 Active"
        return ""
    mock_fs.read_file.side_effect = mock_read

    service = SessionPruningService(mock_config, mock_fs)
    
    items = [
        ContextItem(path="session/01/plan.md", token_count=100, git_status="", scope="Turn"),
        ContextItem(path="session/02/plan.md", token_count=100, git_status="", scope="Turn"),
        ContextItem(path="session/06/plan.md", token_count=100, git_status="", scope="Turn"),
        ContextItem(path="session/07/plan.md", token_count=100, git_status="", scope="Turn"),
        ContextItem(path="session/10/plan.md", token_count=100, git_status="", scope="Turn"),
        ContextItem(path="session/10/report.md", token_count=100, git_status="", scope="Turn"),
        ContextItem(path="session/11/plan.md", token_count=100, git_status="", scope="Turn"),
        ContextItem(path="docs/ARCHITECTURE.md", token_count=500, git_status="", scope="System"),
        ContextItem(path="session/meta.yaml", token_count=50, git_status="", scope="Session"),
    ]
    
    context = ProjectContext(items=items, header="", content="")
    pruned_context = service.prune(context)
    
    plan = Plan(
        title="Unified Context Demo",
        rationale="Demonstrating verification and interaction in one script.",
        actions=[
            ActionData(
                type=ActionType.READ, 
                params={"path": "README.md"}, 
                description="Read the README"
            )
        ],
        metadata={"Agent": "Developer"}
    )
    
    return pruned_context, plan

def run_verification(pruned_context):
    """Phase 1: Heuristic Assertions."""
    print("\n[PHASE 1] Verifying Heuristics...")
    results = {item.path: item for item in pruned_context.items}
    
    # H6: Retention (Max=11, Limit=5 -> Threshold=6)
    assert not results["session/01/plan.md"].selected, "H6 failed: 01 should be pruned"
    assert not results["session/06/plan.md"].selected, "H6 failed: 06 should be pruned"
    
    # H4: Validation Failure
    assert not results["session/10/plan.md"].selected, "H4 failed: 10 should be pruned"
    
    # H3: Preservation
    assert results["session/11/plan.md"].selected, "H3 failed: Latest failure should be preserved"

    print("SUCCESS: All heuristics applied correctly.")

async def run_smoke_test(pruned_context, plan):
    """Phase 2: TUI Smoke Test (Headless)."""
    print("\n[PHASE 2] Smoke Testing TUI (Headless)...")
    app = ReviewerApp(
        plan=plan,
        project_context=pruned_context,
        system_env=MagicMock(),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("ActionTree")
        assert any(node.data == CONTEXT_ROOT for node in tree.root.children)
    print("SUCCESS: TUI initialized and rendered correctly.")

def run_interactive(pruned_context, plan):
    """Phase 3: Interactive Launch."""
    print("\n[PHASE 3] Launching Interactive TUI...")
    app = ReviewerApp(
        plan=plan,
        project_context=pruned_context,
        system_env=MagicMock(),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    
    # ReviewerApp.run() returns the value passed to self.exit()
    submitted_plan = app.run()
    
    if submitted_plan:
        print("\n=== Submission Result ===")
        pruned = submitted_plan.metadata.get("pruned_context", "None")
        print(f"Pruned Context: {pruned}")
    else:
        print("\nExited without submitting.")

if __name__ == "__main__":
    print("=== TeDDy Unified Context Showcase ===")
    p_context, plan = setup_showcase_data()
    
    try:
        run_verification(p_context)
        asyncio.run(run_smoke_test(p_context, plan))
        run_interactive(p_context, plan)
    except Exception as e:
        print(f"\n[ERROR] Showcase Failed: {e}")
        sys.exit(1)