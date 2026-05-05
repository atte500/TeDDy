import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass(frozen=True)
class ContextItem:
    path: str
    token_count: int
    source_scope: str
    git_status: str  # e.g., "M ", "??", "A "
    is_auto_pruned: bool = False

@dataclass(frozen=True)
class ProjectContext:
    header: str
    content: str
    items: List[ContextItem] = field(default_factory=list)
    git_status_raw: Optional[str] = None

def parse_git_status(status_raw: Optional[str]) -> Dict[str, str]:
    """
    Parses 'git status -s' output into a mapping of path -> status code.
    Example: ' M src/main.py\n?? docs/new.md' -> {'src/main.py': 'M ', 'docs/new.md': '??'}
    """
    if not status_raw:
        return {}
    
    status_map = {}
    for line in status_raw.splitlines():
        if len(line) < 4:
            continue
        code = line[:2]
        path = line[3:].strip()
        # Handle cases where path is quoted or has arrows (renames)
        if " -> " in path:
            path = path.split(" -> ")[-1].strip()
        status_map[path] = code
    return status_map

def apply_auto_pruning(
    items: List[ContextItem],
    config: Dict,
    failed_artifacts: List[str]
) -> List[ContextItem]:
    """
    Applies auto-pruning heuristics to context items.
    """
    if not config.get("enabled", True):
        return items

    threshold = config.get("threshold_tokens", 10000)
    prune_failed_plans = config.get("prune_failed_plans", True)
    prune_failed_reports = config.get("prune_failed_reports", True)

    new_items = []
    for item in items:
        # 1. Scope Restriction: session context is never pruned
        if item.source_scope.lower() == "session":
            new_items.append(item)
            continue
        
        is_pruned = False
        
        # 2. Token Threshold
        if item.token_count > threshold:
            is_pruned = True
        
        # 3. Failure Artifacts
        if prune_failed_plans and "plan" in item.path.lower() and item.path in failed_artifacts:
            is_pruned = True
        if prune_failed_reports and "report" in item.path.lower() and item.path in failed_artifacts:
            is_pruned = True
            
        new_items.append(
            ContextItem(
                path=item.path,
                token_count=item.token_count,
                source_scope=item.source_scope,
                git_status=item.git_status,
                is_auto_pruned=is_pruned
            )
        )
    return new_items

# Test the prototype
if __name__ == "__main__":
    raw_status = " M src/teddy_executor/core/services/context_service.py\n?? docs/project/slices/00-04-context-management-ui.md\n D old_file.py"
    status_map = parse_git_status(raw_status)
    print(f"Parsed Git Status: {status_map}")

    items = [
        ContextItem("src/heavy.py", 15000, "Turn", status_map.get("src/heavy.py", "  ")),
        ContextItem("docs/plan.md", 500, "Turn", status_map.get("docs/plan.md", "  ")),
        ContextItem("src/core.py", 2000, "Session", "  "),
        ContextItem("tests/report.md", 1000, "Turn", "  "),
    ]

    config = {
        "enabled": True,
        "threshold_tokens": 10000,
        "prune_failed_plans": True,
        "prune_failed_reports": True
    }
    
    # Simulate identifying failed artifacts (e.g. by reading 'Status: FAILURE')
    failed_artifacts = ["tests/report.md"]
    
    pruned_items = apply_auto_pruning(items, config, failed_artifacts)
    
    print("\nPruning Results:")
    for item in pruned_items:
        status = "[PRUNED]" if item.is_auto_pruned else "[KEEP]"
        print(f"{status} {item.path} ({item.token_count} tokens) Scope: {item.source_scope}")