import yaml
from unittest.mock import MagicMock
from teddy_executor.core.services.session_service import SessionService
from teddy_executor.core.domain.models.execution_report import ExecutionReport


def test_transition_to_next_turn_creates_directory_and_linkage():
    """
    transition_to_next_turn should create a new turn directory (T_next)
    and seed it with metadata linked to the current turn (T_current).
    """
    # Arrange
    fs = MagicMock()
    service = SessionService(file_system_manager=fs)

    # Mock current turn state
    plan_path = ".teddy/sessions/feat-x/01/plan.md"
    current_meta = "turn_id: 'abc'\n"
    current_prompt = "system prompt content"
    current_context = "file_a.py"

    # Mocking FS reads for T_current
    fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": current_meta,
        ".teddy/sessions/feat-x/01/system_prompt.xml": current_prompt,
        ".teddy/sessions/feat-x/01/turn.context": current_context,
    }.get(path, "")

    # Mock directory existence check for T_next
    fs.create_directory.return_value = None

    report = MagicMock(spec=ExecutionReport)
    report.original_actions = []  # No READ/PRUNE actions yet

    # Act
    next_turn_path = service.transition_to_next_turn(plan_path, report)

    # Assert
    assert next_turn_path == ".teddy/sessions/feat-x/02"

    # Verify directory creation
    fs.create_directory.assert_any_call(".teddy/sessions/feat-x/02")

    # Verify meta.yaml linkage (parent_turn_id: 'abc')
    meta_call = next(
        c for c in fs.write_file.call_args_list if "02/meta.yaml" in c.args[0]
    )
    meta_data = yaml.safe_load(meta_call.args[1])
    assert meta_data["parent_turn_id"] == "abc"
    assert meta_data["turn_id"] == "02"

    # Verify system_prompt.xml is copied
    prompt_call = next(
        c for c in fs.write_file.call_args_list if "02/system_prompt.xml" in c.args[0]
    )
    assert prompt_call.args[1] == "system prompt content"

    # Verify report.md is added to context
    context_call = next(
        c for c in fs.write_file.call_args_list if "02/turn.context" in c.args[0]
    )
    assert "01/report.md" in context_call.args[1]


def test_transition_to_next_turn_applies_read_and_prune_side_effects():
    """
    transition_to_next_turn should add READ resources to and remove PRUNE
    resources from the next turn's context.
    """
    # Arrange
    fs = MagicMock()
    service = SessionService(file_system_manager=fs)

    plan_path = ".teddy/sessions/feat-x/01/plan.md"
    current_meta = "turn_id: 'abc'\n"
    current_prompt = "system prompt content"
    current_context = "file_a.py\nfile_b.py"  # file_b.py is in context

    fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": current_meta,
        ".teddy/sessions/feat-x/01/system_prompt.xml": current_prompt,
        ".teddy/sessions/feat-x/01/turn.context": current_context,
    }.get(path, "")

    # Mock Report with READ (new_file.py) and PRUNE (file_b.py)
    report = MagicMock(spec=ExecutionReport)

    # We need to mock the action objects as well
    action_read = MagicMock()
    action_read.type = "READ"
    action_read.params = {"Resource": "[new_file.py](/new_file.py)"}

    action_prune = MagicMock()
    action_prune.type = "PRUNE"
    action_prune.params = {"Resource": "[file_b.py](/file_b.py)"}

    report.original_actions = [action_read, action_prune]

    # Act
    service.transition_to_next_turn(plan_path, report)

    # Assert
    context_call = next(
        c for c in fs.write_file.call_args_list if "02/turn.context" in c.args[0]
    )
    next_context = context_call.args[1]

    assert "file_a.py" in next_context  # Persisted from T_current
    assert "new_file.py" in next_context  # Added via READ
    assert "01/report.md" in next_context  # Always added
    assert "file_b.py" not in next_context  # Removed via PRUNE
