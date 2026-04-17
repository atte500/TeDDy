from enum import Enum
from unittest.mock import MagicMock
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    format_node_label,
)


class MockActionType(Enum):
    CREATE = "CREATE"


def test_format_node_label_stringifies_enums():
    # Setup
    action = MagicMock()
    action.type = MockActionType.CREATE
    action.description = "test.txt"
    action.selected = True
    action.executed = False
    action.modified = False

    # Driver
    label = format_node_label(action)

    # Observer: Should not contain "MockActionType.CREATE"
    assert "CREATE: test.txt" in label
    assert "MockActionType" not in label
