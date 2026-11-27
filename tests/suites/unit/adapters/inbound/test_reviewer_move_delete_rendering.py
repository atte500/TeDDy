"""Presentation wiring for MOVE and DELETE in the plan reviewer.

A reviewer must see both verbs' parameters, must be able to tell a rename from a
plain path, and must never have an edited ``Recursive: false`` reach the
filesystem port as a truthy string.
"""

import pytest

from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    _apply_param_edit,
    format_node_label,
)
from teddy_executor.core.domain.models.plan import ActionData


@pytest.mark.parametrize(
    ("action_type", "key"),
    [
        pytest.param("DELETE", "recursive", id="delete-recursive"),
        pytest.param("CREATE", "overwrite", id="create-overwrite"),
        pytest.param("EDIT", "match_all", id="edit-match-all"),
        pytest.param("EXECUTE", "allow_failure", id="execute-allow-failure"),
        pytest.param("EXECUTE", "background", id="execute-background"),
    ],
)
def test_inline_edit_writes_false_back_as_a_boolean(action_type, key):
    """A reviewer sparing a subtree must not leave a truthy string behind."""
    action = ActionData(type=action_type, params={})

    _apply_param_edit(action, key, "false")

    assert action.params[key] is False


def test_inline_edit_writes_true_back_as_a_boolean():
    """The affirmative direction follows the same rule, case-insensitively."""
    action = ActionData(type="DELETE", params={"path": "a/legacy"})

    _apply_param_edit(action, "recursive", "TRUE")

    assert action.params["recursive"] is True


def test_move_label_names_both_paths_in_plan_order():
    """A rename is identified by its pair, not by the source alone."""
    action = ActionData(
        type="MOVE",
        params={"source": "a/old.py", "destination": "a/new.py"},
    )

    label = format_node_label(action)

    assert label.index("a/old.py") < label.index("a/new.py")
