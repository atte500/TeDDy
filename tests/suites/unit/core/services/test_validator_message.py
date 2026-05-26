from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


def test_validate_message_requires_content(container):
    validator = container.resolve(IPlanValidator)

    # Case 1: Missing content
    plan_missing = Plan(
        title="Test", rationale="Test", actions=[ActionData(type="MESSAGE", params={})]
    )
    errors = validator.validate(plan_missing)
    assert any(
        "MESSAGE action must have non-empty content" in e.message for e in errors
    )

    # Case 2: Empty content
    plan_empty = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="MESSAGE", params={"content": "  "})],
    )
    errors = validator.validate(plan_empty)
    assert any(
        "MESSAGE action must have non-empty content" in e.message for e in errors
    )

    # Case 3: Valid content
    plan_valid = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="MESSAGE", params={"content": "Hello world"})],
    )
    errors = validator.validate(plan_valid)
    # Filter for MESSAGE related errors
    msg_errors = [e for e in errors if "MESSAGE" in e.message]
    assert not msg_errors
