"""Test that SessionPruningService respects preserve_message_turns in global budget pruning."""

import punq
from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from tests.harness.setup.mocking import register_mock
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


class TestPreserveMessageTurnsGlobalBudget:
    """When preserve_message_turns is True, items from message turns must survive global budget pruning."""

    def _make_item(
        self,
        path: str,
        scope: str = "Turn",
        token_count: int = 1000,
        selected: bool = True,
        git_status: str = " ",
    ) -> ContextItem:
        """Create a minimal ContextItem with required fields."""
        return ContextItem(
            path=path,
            scope=scope,
            token_count=token_count,
            selected=selected,
            git_status=git_status,
        )

    def test_global_budget_respects_spared_message_turns(self):
        """Set global_context_threshold low, expect non-message turn pruned, message turn spared."""
        container = punq.Container()
        config_svc = register_mock(container, IConfigService)
        fs_mock = register_mock(container, IFileSystemManager)

        # Config: enable auto-pruning, preserve message turns, threshold=500
        config_svc.get_setting.side_effect = lambda key, default=None: {
            "auto_pruning.enabled": True,
            "auto_pruning.prune_failure_history": True,
            "auto_pruning.prune_validation_failures": True,
            "auto_pruning.preserve_message_turns": True,
            "auto_pruning.global_context_threshold": 500,
            "auto_pruning.max_turns_retention": 0,
        }.get(key, default)

        svc = SessionPruningService(
            config_service=config_svc,
            file_system_manager=fs_mock,
        )

        # Create a ProjectContext with two Turn items:
        # - A regular turn plan.md (will be pruned)
        # - A message turn plan.md (should be spared)
        regular_item = self._make_item(
            path=".teddy/sessions/test/01/plan.md", token_count=1000
        )
        message_item = self._make_item(
            path=".teddy/sessions/test/02/plan.md", token_count=1000
        )

        # Simulate context
        context = ProjectContext(
            items=[regular_item, message_item],
            header="",
            content="",
        )

        # Mock plan file contents:
        # - Turn 01 plan does NOT contain "## Message" -> regular
        # - Turn 02 plan does contain "## Message" -> message turn
        fs_mock.path_exists.return_value = True

        def read_file(path: str) -> str:
            if "02/plan.md" in str(path):
                return "# Title\n## Message\nHandoff content."
            if "02/report.md" in str(path):
                return "# Report\n- **Overall Status:** SUCCESS"
            return "# Title\n## Action Plan\n\n### `READ`\n..."

        fs_mock.read_file.side_effect = read_file

        # Act
        result = svc.prune(context)

        # Assert
        # Turn 02 (message turn) should remain selected
        msg_item = next((i for i in result.items if "02/plan.md" in i.path), None)
        assert msg_item is not None, "Message turn item must exist"
        assert msg_item.selected is True, (
            "Message turn must NOT be pruned by global budget "
            "when preserve_message_turns is True"
        )

        # Turn 01 (regular) should be pruned
        reg_item = next((i for i in result.items if "01/plan.md" in i.path), None)
        assert reg_item is not None, "Regular turn item must exist"
        assert reg_item.selected is False, (
            "Regular turn should be pruned by global budget"
        )
