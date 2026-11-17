from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


def test_parser_retains_plan_path():
    parser = MarkdownPlanParser()
    plan_content = """# Test Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Pathfinder

## Rationale
```text
### Summary
Test
### Expectation
Test
### Progress
Test
### Notes
Test
```

## Action Plan
### `EXECUTE`
- Description: Test
```shell
ls
```
"""
    plan_path = "/tmp/test_plan.md"

    # Act
    plan = parser.parse(plan_content, plan_path=plan_path)

    # Assert
    assert hasattr(plan, "plan_path"), "Plan object should have a plan_path attribute"
    assert plan.plan_path == plan_path, (
        f"Expected plan_path {plan_path}, got {plan.plan_path}"
    )
