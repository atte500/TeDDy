import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Sequence

# -------------------------------------------------------------
# 1. New Core Logic & Helpers
# -------------------------------------------------------------

def get_session_history_display_name(path: str) -> Optional[str]:
    """Returns human-readable display name if it's a recognized session history file."""
    # Strip leading slash/dot-slashes for consistent checking
    clean_path = path.lstrip("./")
    if "initial_request.md" in clean_path:
        return "Initial Request"
    plan_match = re.search(r"sessions/[^/]+/(\d+)/plan.md$", clean_path)
    if plan_match:
        return f"Turn {int(plan_match.group(1))}: Plan"
    report_match = re.search(r"sessions/[^/]+/(\d+)/report.md$", clean_path)
    if report_match:
        return f"Turn {int(report_match.group(1))}: Execution Report"
    return None

def is_session_file_path(path: str) -> bool:
    """Determines if a path is inside .teddy/sessions/."""
    return "sessions/" in path.lstrip("./")

def is_session_history_path(path: str) -> bool:
    """Determines if a path is a session history file."""
    return get_session_history_display_name(path) is not None

def get_session_history_sort_key(path: str) -> tuple[int, int]:
    """Sort key for chronological session history: (turn_number, sub_order)."""
    clean_path = path.lstrip("./")
    if "initial_request.md" in clean_path:
        return (0, 0)
    plan_match = re.search(r"sessions/[^/]+/(\d+)/plan.md$", clean_path)
    if plan_match:
        return (int(plan_match.group(1)), 1)
    report_match = re.search(r"sessions/[^/]+/(\d+)/report.md$", clean_path)
    if report_match:
        return (int(report_match.group(1)), 2)
    return (999999, 999999)

# -------------------------------------------------------------
# 2. Monkey-patching ContextService
# -------------------------------------------------------------
from teddy_executor.core.services.context_service import ContextService

# Store original methods
_orig_format_content = ContextService._format_content
_orig_format_resource_contents = ContextService._format_resource_contents

def patched_format_content(
    self,
    repo_tree: str,
    scoped_paths: Dict[str, List[str]],
    file_contents: Dict[str, Optional[str]],
    git_status: Optional[str] = None,
) -> str:
    # 1. Gather all unique paths
    all_paths: List[str] = []
    for paths in scoped_paths.values():
        for p in paths:
            if p not in all_paths:
                all_paths.append(p)

    # 2. Filter out session history files from standard workspace content
    workspace_paths = [p for p in all_paths if "sessions/" not in p.lstrip("./")]
    session_paths = [p for p in all_paths if "sessions/" in p.lstrip("./")]

    # Sort session history files chronologically
    session_paths.sort(key=get_session_history_sort_key)

    # 3. Format git status & project structure
    display_status = git_status
    if git_status == "":
        display_status = "nothing to commit, working tree clean"

    content_parts = [
        "\n## 2. Git Status",
        display_status if display_status is not None else "",
        "\n## 3. Project Structure",
        f"```\n{repo_tree}\n```",
    ]

    # 4. Format standard workspace resource contents
    if workspace_paths:
        content_parts.append("\n## 4. Resource Contents")
        from teddy_executor.core.utils.markdown import (
            get_fence_for_content,
            get_language_from_path,
        )
        for path in workspace_paths:
            content_parts.append("\n---")
            content_parts.append(f"### [{path}](/{path})")
            content = file_contents.get(path)
            if content is not None:
                lang = get_language_from_path(path)
                fence = get_fence_for_content(content)
                content_parts.append(f"{fence}{lang}\n{content}\n{fence}")
            else:
                content_parts.append("```\n--- FILE NOT FOUND ---\n```")

    # 5. Build Session History Section if there are any session paths
    # (Checking if any session paths are present to ensure backward compatibility)
    if session_paths:
        has_history = False
        history_parts = ["\n## 5. Session History"]
        from teddy_executor.core.utils.markdown import (
            get_fence_for_content,
            get_language_from_path,
        )
        for p in session_paths:
            disp_name = get_session_history_display_name(p)
            if disp_name:  # Only include recognized conversation turns (exclude meta.yaml etc.)
                has_history = True
                content = file_contents.get(p) or ""
                lang = get_language_from_path(p)
                fence = get_fence_for_content(content)
                history_parts.append(f"\n### {disp_name}")
                history_parts.append(f"{fence}{lang}\n{content.strip()}\n{fence}")
        
        if has_history:
            content_parts.extend(history_parts)

    return "\n".join(content_parts)

ContextService._format_content = patched_format_content

# -------------------------------------------------------------
# 3. Monkey-patching Textual review app logic and helpers
# -------------------------------------------------------------
import teddy_executor.adapters.inbound.textual_plan_reviewer_helpers as helpers
import teddy_executor.adapters.inbound.textual_plan_reviewer_logic as logic

# Define HISTORY_LABEL
HISTORY_LABEL = "HISTORY_LABEL"
logic.HISTORY_LABEL = HISTORY_LABEL

# Store original _is_context_data and populate_context_detail
_orig_is_context_data = logic._is_context_data
_orig_populate_context_detail = helpers.populate_context_detail
_orig_format_context_item_label = helpers.format_context_item_label

def patched_is_context_data(data: Any) -> bool:
    from teddy_executor.core.domain.models.project_context import ContextItem
    return (
        data in (logic.CONTEXT_ROOT, logic.SYSTEM_LABEL, logic.SESSION_LABEL, logic.TURN_LABEL, HISTORY_LABEL)
        or isinstance(data, ContextItem)
        or (isinstance(data, dict) and data.get("type") == "SYSTEM_PROMPT")
    )

def patched_format_context_item_label(item: Any) -> str:
    status_colors = {
        "M": "yellow",
        "??": "green",
        "A": "green",
        "D": "red",
        "U": "green",
    }
    clean_status = item.git_status.strip()
    display_status = "U" if clean_status == "??" else clean_status
    status_part = (
        f" [[{status_colors.get(clean_status, 'white')}]{display_status}[/]]"
        if clean_status
        else ""
    )
    token_str = f"{item.token_count / 1000.0:.1f}k"
    
    # Check if this is a session history file to use a clean display name
    disp_name = get_session_history_display_name(item.path)
    display_path = disp_name if disp_name else item.path

    if not item.selected:
        return f"  [s dim]{display_path}{status_part} {token_str}[/]"
    return f"  [bold]{display_path}[/]{status_part} [#888888]{token_str}[/]"

def patched_populate_context_detail(app: Any, pane: Any, data: Any) -> None:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import DetailItem
    from teddy_executor.core.domain.models.project_context import ContextItem

    if isinstance(data, ContextItem):
        disp_name = get_session_history_display_name(data.path)
        path_label = disp_name if disp_name else data.path
        pane.append(DetailItem("Path", path_label))
        pane.append(DetailItem("Tokens", f"{data.token_count / 1000.0:.1f}k"))
        status_map = {
            "M": "Modified",
            "??": "Untracked",
            "U": "Untracked",
            "A": "Added",
            "D": "Deleted",
        }
        status_text = status_map.get(data.git_status.strip(), "Unmodified")
        pane.append(DetailItem("Git Status", status_text))
        pane.append(DetailItem("Scope", data.scope))
        if data.auto_prune_reason:
            pane.append(DetailItem("Auto-Prune", data.auto_prune_reason))
    elif isinstance(data, dict) and data.get("type") == "SYSTEM_PROMPT":
        pane.append(DetailItem("Agent", data.get("agent", "Unknown")))
        pane.append(DetailItem("Tokens", f"{data.get('tokens', 0) / 1000.0:.1f}k"))
    elif app.project_context:
        # Context Aggregate View - Only sum SELECTED items
        selected_items = [i for i in app.project_context.items if i.selected]
        total_tokens = (
            sum(i.token_count for i in selected_items)
            + app.project_context.system_prompt_tokens
        )
        pane.append(
            DetailItem(
                "Total Context",
                f"{total_tokens / 1000.0:.1f}k / {app.project_context.total_window / 1000.0:.0f}k tokens",
            )
        )
        pane.append(
            DetailItem(
                "• System", f"{app.project_context.system_prompt_tokens / 1000.0:.1f}k"
            )
        )
        # Separate standard Session/Turn from History items
        session_tokens = sum(i.token_count for i in selected_items if i.scope == 'Session' and not is_session_history_path(i.path))
        turn_tokens = sum(i.token_count for i in selected_items if i.scope == 'Turn' and not is_session_history_path(i.path))
        history_tokens = sum(i.token_count for i in selected_items if is_session_history_path(i.path))

        pane.append(DetailItem("• Session", f"{session_tokens / 1000.0:.1f}k"))
        pane.append(DetailItem("• Turn", f"{turn_tokens / 1000.0:.1f}k"))
        pane.append(DetailItem("• History", f"{history_tokens / 1000.0:.1f}k"))

def patched_build_context_section(app: Any, tree: Any) -> Any:
    if not app.project_context:
        return None

    con_root = tree.root.add("[bold]Context[/]", data=logic.CONTEXT_ROOT, expand=False)
    con_root.add_leaf("[#888888 italic]System:[/]", data=logic.SYSTEM_LABEL)
    token_str = f" [#888888]{app.project_context.system_prompt_tokens / 1000.0:.1f}k[/]"
    con_root.add_leaf(
        f"  [bold]{app.project_context.agent_name}[/]{token_str}",
        data={
            "type": "SYSTEM_PROMPT",
            "agent": app.project_context.agent_name,
            "tokens": app.project_context.system_prompt_tokens,
        },
    )

    # 1. Session folder (excl. history/session files)
    con_root.add_leaf("[#888888 italic]Session:[/]", data=logic.SESSION_LABEL)
    session_count = 0
    for item in app.project_context.items:
        if item.scope == "Session" and not is_session_file_path(item.path):
            con_root.add_leaf(helpers.format_context_item_label(item), data=item)
            session_count += 1
    if session_count == 0:
        con_root.add_leaf("  [#888888](None)[/]", data=logic.SESSION_LABEL)

    # 2. Turn folder (excl. history/session files)
    con_root.add_leaf("[#888888 italic]Turn:[/]", data=logic.TURN_LABEL)
    turn_count = 0
    for item in app.project_context.items:
        if item.scope == "Turn" and not is_session_file_path(item.path):
            con_root.add_leaf(helpers.format_context_item_label(item), data=item)
            turn_count += 1
    if turn_count == 0:
        con_root.add_leaf("  [#888888](None)[/]", data=logic.TURN_LABEL)

    # 3. History folder (incl. history)
    history_items = [item for item in app.project_context.items if is_session_history_path(item.path)]
    if history_items:
        con_root.add_leaf("[#888888 italic]History:[/]", data=HISTORY_LABEL)
        # Sort history items chronologically using our key sorting helper
        history_items.sort(key=lambda x: get_session_history_sort_key(x.path))
        for item in history_items:
            con_root.add_leaf(helpers.format_context_item_label(item), data=item)

    return con_root

logic._is_context_data = patched_is_context_data
helpers.populate_context_detail = patched_populate_context_detail
helpers.format_context_item_label = patched_format_context_item_label
helpers.build_context_section = patched_build_context_section

# -------------------------------------------------------------
# 4. Programmatic Assertions / Sanity Checks (Jidoka)
# -------------------------------------------------------------

def run_sanity_checks():
    print("=== Running Programmatic Sanity Checks ===")

    # Setup mock dependencies
    class MockFileSystemManager:
        def read_file(self, path):
            return f"Content of {path}"
        def path_exists(self, path):
            return True
        def read_files_in_vault(self, paths):
            contents = {}
            for p in paths:
                if "initial_request" in p:
                    contents[p] = "Implement user login"
                elif "plan.md" in p:
                    contents[p] = "Plan for step 1"
                elif "report.md" in p:
                    contents[p] = "Report for step 1"
                else:
                    contents[p] = f"Content of {Path(p).name}"
            return contents

    class MockRepoTreeGenerator:
        def generate_tree(self):
            return "src/\n  main.py"

    class MockEnvironmentInspector:
        def get_environment_info(self):
            return {
                "current_date": "2026-05-21",
                "current_time": "14:09:14",
                "cwd": "/workspace",
                "os_name": "Darwin",
                "os_version": "25.2.0",
                "shell": "/bin/zsh",
            }
        def get_git_status(self):
            return "nothing to commit, working tree clean"

    class MockLlmClient:
        def get_text_token_count(self, text):
            return len(text) * 10  # simulated tokens

    # Instantiate patched ContextService
    fs = MockFileSystemManager()
    tree_gen = MockRepoTreeGenerator()
    inspector = MockEnvironmentInspector()
    llm = MockLlmClient()

    service = ContextService(fs, tree_gen, inspector, llm)

    # Define mock context files in a session
    context_files = {
        "Session": [
            ".teddy/sessions/20260521_134944-test-session/initial_request.md",
            ".teddy/sessions/20260521_134944-test-session/01/meta.yaml",  # unrecognized
        ],
        "Turn": [
            ".teddy/sessions/20260521_134944-test-session/01/plan.md",
            ".teddy/sessions/20260521_134944-test-session/01/report.md",
            "src/main.py",  # normal file
        ]
    }

    # Override service's path resolution for isolated testing
    def mock_resolve_scoped_paths(files):
        # Flatten all values
        flat = []
        for v in files.values():
            flat.extend(v)
        return files, flat
    service._resolve_scoped_paths = mock_resolve_scoped_paths

    # Get project context DTO
    context = service.get_context(context_files=context_files, include_tokens=True)

    # --- ASSERTIONS FOR SCENARIO 1 ---
    print("Verifying Scenario 1: Context Payload Formatting...")
    print("\n--- VISUAL INSPECTION OF FORMATTED PAYLOAD ---")
    print(context.content)
    print("-----------------------------------------------\n")
    
    # 1. Session files must NOT be present in Resource Contents
    assert "## 4. Resource Contents" in context.content
    assert "### [src/main.py]" in context.content
    assert "initial_request.md" not in context.content.split("## 4. Resource Contents")[1].split("## 5. Session History")[0]
    assert "plan.md" not in context.content.split("## 4. Resource Contents")[1].split("## 5. Session History")[0]
    assert "report.md" not in context.content.split("## 4. Resource Contents")[1].split("## 5. Session History")[0]
    assert "meta.yaml" not in context.content

    # 2. Session History must be present at the end
    assert "## 5. Session History" in context.content
    history_part = context.content.split("## 5. Session History")[1]

    # 3. Exact chronological ordering: Initial Request -> Turn 1: Plan -> Turn 1: Execution Report
    assert "### Initial Request" in history_part
    assert "### Turn 1: Plan" in history_part
    assert "### Turn 1: Execution Report" in history_part

    # Index order check
    idx_req = history_part.index("### Initial Request")
    idx_plan = history_part.index("### Turn 1: Plan")
    idx_report = history_part.index("### Turn 1: Execution Report")
    assert idx_req < idx_plan < idx_report

    # 4. Must NOT contain raw paths or links under .teddy/sessions/
    assert ".teddy/sessions/" not in history_part

    print("✓ Scenario 1 Verified Successfully!")

    # --- ASSERTIONS FOR SCENARIO 2 ---
    print("Verifying Scenario 2: TUI Tree Node Construction...")
    
    class MockNode:
        def __init__(self, label, data=None):
            self.label = label
            self.data = data
            self.children = []
        def add(self, label, data=None, expand=False):
            n = MockNode(label, data)
            self.children.append(n)
            return n
        def add_leaf(self, label, data=None):
            n = MockNode(label, data)
            self.children.append(n)
            return n

    class MockTree:
        def __init__(self):
            self.root = MockNode("Root")

    class MockApp:
        def __init__(self, context_dto):
            self.project_context = context_dto

    mock_app = MockApp(context)
    mock_tree = MockTree()

    # Call build_context_section
    helpers.build_context_section(mock_app, mock_tree)

    # Verify context root and children
    context_root_node = mock_tree.root.children[0]
    assert "Context" in context_root_node.label

    # Check that .teddy/sessions files are NOT under Session or Turn labels
    session_label_node = None
    turn_label_node = None
    history_label_node = None

    for child in context_root_node.children:
        if "Session:" in child.label:
            session_label_node = child
        elif "Turn:" in child.label:
            turn_label_node = child
        elif "History:" in child.label:
            history_label_node = child

    # Retrieve all leaves following those markers
    idx_session = context_root_node.children.index(session_label_node)
    idx_turn = context_root_node.children.index(turn_label_node)
    idx_history = context_root_node.children.index(history_label_node)

    # Leaves under Session:
    session_leaves = context_root_node.children[idx_session+1 : idx_turn]
    # Leaves under Turn:
    turn_leaves = context_root_node.children[idx_turn+1 : idx_history]
    # Leaves under History:
    history_leaves = context_root_node.children[idx_history+1 :]

    # Assert session and turn lists are empty of session paths (meta.yaml and sessions paths excluded)
    # The only item in Turn is src/main.py
    assert len(session_leaves) == 1
    assert "None" in session_leaves[0].label  # default fallback
    
    assert len(turn_leaves) == 1
    assert "src/main.py" in turn_leaves[0].label

    # Assert History folder exists and displays nodes in correct order with names and token counts
    assert history_label_node is not None
    assert "History:" in history_label_node.label
    assert len(history_leaves) == 3
    assert "Initial Request" in history_leaves[0].label
    assert "Turn 1: Plan" in history_leaves[1].label
    assert "Turn 1: Execution Report" in history_leaves[2].label

    print("✓ Scenario 2 Verified Successfully!")

    # --- ASSERTIONS FOR SCENARIO 3 ---
    print("Verifying Scenario 3: Right-pane aggregates with toggling...")
    
    # Let's mock a pane we can append aggregates into
    class MockAggregatePane:
        def __init__(self):
            self.items = []
        def append(self, item):
            self.items.append(item)
        def clear(self):
            self.items = []

    pane = MockAggregatePane()
    patched_populate_context_detail(mock_app, pane, data=None)

    # Find total tokens in pane items
    total_aggregate = next(item for item in pane.items if item.data["key"] == "Total Context")
    session_aggregate = next(item for item in pane.items if item.data["key"] == "• Session")
    turn_aggregate = next(item for item in pane.items if item.data["key"] == "• Turn")
    history_aggregate = next(item for item in pane.items if item.data["key"] == "• History")

    # Initially all are selected:
    # main.py is in context.items
    # initial_request.md, plan.md, report.md are in context.items
    # Let's count totals
    initial_total_val = total_aggregate.data["val"]
    initial_history_val = history_aggregate.data["val"]

    # Now toggle the "Turn 1: Plan" context item to deselect it
    plan_item = next(i for i in context.items if "01/plan.md" in i.path)
    plan_item.selected = False

    # Refresh aggregates
    pane.clear()
    patched_populate_context_detail(mock_app, pane, data=None)

    new_total_aggregate = next(item for item in pane.items if item.data["key"] == "Total Context")
    new_history_aggregate = next(item for item in pane.items if item.data["key"] == "• History")

    # Assert aggregate totals updated immediately to exclude the item's token count
    assert new_total_aggregate.data["val"] != initial_total_val
    assert new_history_aggregate.data["val"] != initial_history_val
    print("✓ Scenario 3 Verified Successfully!")

    print("All programmatical sanity checks passed!")

# Mock classes to supply required constructor arguments to ReviewerApp
class MockSystemEnvironment:
    def delete_file(self, path: str) -> None:
        pass

class MockConsoleTooling:
    pass

class MockActionDispatcher:
    pass

# -------------------------------------------------------------
# 5. Non-Interactive Smoke Test & Interactive Showcase TUI Mode (Showcase Gate)
# -------------------------------------------------------------

def get_showcase_data():
    from teddy_executor.core.domain.models import Plan, ActionData
    from teddy_executor.core.domain.models.project_context import ProjectContext, ContextItem

    # Create a minimal Plan structure for the TUI
    actions = [
        ActionData(type="CREATE", params={"path": "src/main.py"}, description="Create main.py entrypoint"),
        ActionData(type="EXECUTE", params={"command": "pytest"}, description="Run test suite"),
    ]
    plan = Plan(
        title="Chronological Session History Demo",
        rationale="### Synthesis\nThis is a demo of the new chronological history grouping inside the review TUI.\n\n### Justification\nWe grouped the session history under History: folder to avoid clutter.",
        actions=actions,
        metadata={"Agent": "Prototyper", "Plan Type": "Showcase", "Status": "Active 🟢"},
        is_session=True,
    )

    # Populate a real mock ProjectContext with history items
    items = [
        ContextItem(path=".teddy/sessions/20260521_134944-test-session/initial_request.md", token_count=1200, git_status=" ", scope="Session"),
        ContextItem(path=".teddy/sessions/20260521_134944-test-session/01/plan.md", token_count=4500, git_status=" ", scope="Turn"),
        ContextItem(path=".teddy/sessions/20260521_134944-test-session/01/report.md", token_count=3200, git_status=" ", scope="Turn"),
        ContextItem(path="src/main.py", token_count=2500, git_status="M", scope="Turn"),
    ]

    project_context = ProjectContext(
        header="# Project Context",
        content="Dummy content",
        scoped_paths={"Session": [], "Turn": []},
        git_status="M src/main.py",
        items=items,
        agent_name="Prototyper",
        system_prompt_tokens=5000,
        total_window=32000,
    )
    return plan, project_context

def launch_interactive_showcase():
    """Launches an interactive Textual Plan Reviewer UI using our patched logic."""
    print("Launching Interactive TUI Showcase...")
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    plan, project_context = get_showcase_data()

    app = ReviewerApp(
        plan=plan,
        system_env=MockSystemEnvironment(),
        console_tooling=MockConsoleTooling(),
        action_dispatcher=MockActionDispatcher(),
        project_context=project_context,
    )
    app.run()

if __name__ == "__main__":
    run_sanity_checks()
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        launch_interactive_showcase()
    else:
        print("\nSanity checks passed! Run with '--interactive' to launch the interactive UI showcase.")