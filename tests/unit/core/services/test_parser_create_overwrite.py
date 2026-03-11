from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


def test_parse_create_action_extracts_overwrite_parameter():
    # Given a plan with a CREATE action containing Overwrite: true
    plan_content = """# Test Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Test.
### 2. Justification
Test.
### 3. Expected Outcome
Test.
### 4. State Dashboard
Test.
```

## Action Plan

### `CREATE`
- File Path: [new.txt](/new.txt)
- Overwrite: true
- Description: Overwrite test.
```text
content
```
"""
    parser = MarkdownPlanParser()

    # When parsing the plan
    plan = parser.parse(plan_content)

    # Then the CREATE action should have overwrite=True in its params
    action = plan.actions[0]
    assert action.type == "CREATE"
    assert action.params.get("overwrite") is True


def test_parse_create_action_defaults_overwrite_to_false_if_missing():
    # Given a plan with a CREATE action WITHOUT Overwrite
    plan_content = """# Test Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
Rationale
```

## Action Plan

### `CREATE`
- File Path: [new.txt](/new.txt)
- Description: Standard create.
```text
content
```
"""
    parser = MarkdownPlanParser()

    # When parsing the plan
    plan = parser.parse(plan_content)

    # Then the CREATE action should NOT have overwrite=True
    action = plan.actions[0]
    # It can be either False or missing depending on implementation,
    # but for validation logic, we treat missing as False.
    assert action.params.get("overwrite") in (False, None)
