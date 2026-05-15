import unittest
from unittest.mock import MagicMock
from dataclasses import dataclass
from typing import List, Optional

# Mocking domain models locally for the spike to ensure constructor compatibility
@dataclass
class ContextItem:
    path: str
    scope: str
    token_count: int
    selected: bool
    git_status: str
    auto_prune_reason: Optional[str] = None

@dataclass
class ProjectContext:
    items: List[ContextItem]
    header: str
    content: str
    agent_name: str = "pf"
    system_prompt_tokens: int = 0
    total_window: int = 128000

from spikes.debug.shadow_session_pruning_service import ShadowSessionPruningService

class TestPruningRepro(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.config.get_setting.side_effect = lambda key, default: default
        self.fs = MagicMock()
        self.service = ShadowSessionPruningService(self.config, self.fs)

    def test_recovery_cleanup_lag(self):
        # Scenario:
        # Turn 01: FAILURE 🔴
        # Turn 02: SUCCESS 🟢
        # Turn 03: Planned (The one being reviewed now)
        
        items = [
            ContextItem(path="01/plan.md", scope="Turn", token_count=100, selected=True, git_status=""),
            ContextItem(path="01/report.md", scope="Turn", token_count=100, selected=True, git_status=""),
            ContextItem(path="02/plan.md", scope="Turn", token_count=100, selected=True, git_status=""),
            ContextItem(path="02/report.md", scope="Turn", token_count=100, selected=True, git_status=""),
            ContextItem(path="03/plan.md", scope="Turn", token_count=100, selected=True, git_status=""),
        ]

        def mock_read(path):
            if "01/plan.md" in path: return "- **Status:** FAILURE 🔴"
            if "02/plan.md" in path: return "- **Status:** SUCCESS 🟢"
            if "03/plan.md" in path: return "- **Status:** Planned"
            return ""

        self.fs.path_exists.return_value = True
        self.fs.read_file.side_effect = mock_read

        # Use the actual model if imported, but here we use mock for isolation
        context = ProjectContext(items=items, header="", content="")
        result = self.service.prune(context)

        # In Turn 03, the latest turn is 03. 03 is "Planned" (no emoji).
        # SessionPruningService._collect_turn_metadata: 
        #   is_green = not self._check_file_contains(item.path, ("🔴", "🟡"))
        # So Turn 03 IS considered Green.
        # Latest turn is 03. Turn 03 is Green. 
        # Thus, Turn 01 (Non-Green) SHOULD be pruned.
        t1_plan = next(i for i in result.items if i.path == "01/plan.md")
        self.assertFalse(t1_plan.selected, "Turn 01 should be pruned in Turn 03")

    def test_fragility_emoji_in_rationale(self):
        # Scenario: Turn 01 is SUCCESS, but AI mentioned failure in rationale.
        items = [
            ContextItem(path="01/plan.md", scope="Turn", token_count=100, selected=True, git_status=""),
            ContextItem(path="02/plan.md", scope="Turn", token_count=100, selected=True, git_status=""),
        ]
        
        def mock_read(path):
            if "01/plan.md" in path: 
                return "## Rationale\nWe fixed the 🔴 error.\n- **Status:** SUCCESS 🟢"
            if "02/plan.md" in path: return "- **Status:** Planned"
            return ""

        self.fs.path_exists.return_value = True
        self.fs.read_file.side_effect = mock_read
        
        context = ProjectContext(items=items, header="", content="")
        result = self.service.prune(context)
        
        # With the fix, Turn 01 should NOT be pruned because detection is robust.
        t1_plan = next(i for i in result.items if i.path == "01/plan.md")
        self.assertTrue(t1_plan.selected, "Turn 01 should NOT be pruned; detection is now robust")

    def test_immediate_cleanup_with_current_status(self):
        # Scenario:
        # Turn 01: FAILURE 🔴
        # Turn 02: (Current) SUCCESS 🟢 (Being reviewed now)
        items = [
            ContextItem(path="01/plan.md", scope="Turn", token_count=100, selected=True, git_status=""),
            ContextItem(path="02/plan.md", scope="Turn", token_count=100, selected=True, git_status=""),
        ]
        def mock_read(path):
            if "01/plan.md" in path: return "- **Status:** FAILURE 🔴"
            if "02/plan.md" in path: return "- **Status:** Planned"
            return ""
        self.fs.path_exists.return_value = True
        self.fs.read_file.side_effect = mock_read
        
        context = ProjectContext(items=items, header="", content="")
        # Triggering prune with awareness that current status is SUCCESS
        result = self.service.prune(context, current_status="SUCCESS 🟢")
        
        t1_plan = next(i for i in result.items if i.path == "01/plan.md")
        self.assertFalse(t1_plan.selected, "Turn 01 should be pruned IMMEDIATELY when current turn is Green")

if __name__ == "__main__":
    unittest.main()