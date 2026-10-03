from unittest.mock import Mock

from teddy_executor.core.domain.models import ChangeSet
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.outbound import (
    IConfigService,
    IFileSystemManager,
    IUserInteractor,
)

from tests.harness.setup.harness_plan_reviewer import HarnessPlanReviewer


def _build_reviewer():
    """Constructs a HarnessPlanReviewer over strictly spec-bound port doubles."""
    interactor = Mock(spec=IUserInteractor)
    file_system = Mock(spec=IFileSystemManager)
    config = Mock(spec=IConfigService)
    edit_simulator = Mock(spec=IEditSimulator)
    reviewer = HarnessPlanReviewer(
        user_interactor=interactor,
        file_system_manager=file_system,
        config_service=config,
        edit_simulator=edit_simulator,
    )
    return reviewer, interactor, file_system


def _create_action() -> ActionData:
    return ActionData(
        type="CREATE",
        params={"path": "test.txt", "content": "new content"},
        description="Create a test file",
    )


def test_harness_plan_reviewer_conforms_to_port():
    reviewer, _, _ = _build_reviewer()

    assert isinstance(reviewer, IPlanReviewer)


def test_review_returns_plan_without_bulk_summary():
    reviewer, interactor, _ = _build_reviewer()
    plan = Plan(
        title="Test Plan",
        rationale="Test Rationale",
        actions=[_create_action()],
    )

    result = reviewer.review(plan)

    assert result is plan
    interactor.confirm_action.assert_not_called()


def test_review_action_delegates_to_confirm_action():
    reviewer, interactor, file_system = _build_reviewer()
    interactor.confirm_action.return_value = (True, "captured")
    file_system.path_exists.return_value = False

    action = _create_action()

    approved, message = reviewer.review_action(action, total_actions=1)

    assert (approved, message) == (True, "captured")
    assert action.selected is True
    _, kwargs = interactor.confirm_action.call_args
    assert kwargs["action"] is action
    assert "Action: CREATE" in kwargs["action_prompt"]
    assert "path: test.txt" in kwargs["action_prompt"]
    assert isinstance(kwargs["change_set"], ChangeSet)
    assert kwargs["change_set"].action_type == "CREATE"


def test_review_action_sets_selected_false_on_denial():
    reviewer, interactor, file_system = _build_reviewer()
    interactor.confirm_action.return_value = (False, "reason")
    file_system.path_exists.return_value = False

    action = _create_action()

    result = reviewer.review_action(action, total_actions=1)

    assert result == (False, "reason")
    assert action.selected is False
