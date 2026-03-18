from teddy_executor.core.ports.inbound.plan_parser import IPlanParser


def test_multiline_research_parsing(container):
    """
    Scenario 2: Multi-line RESEARCH Handling
    Given a RESEARCH block containing multiple lines of queries
    When the plan is parsed
    Then the queries parameter should contain a list of individual queries, one per line.
    """
    # Arrange
    parser = container.resolve(IPlanParser)
    plan_content = """
# Research Task
- Status: Green 🟢
- Agent: Pathfinder

## Rationale
```text
Rationale
```

## Action Plan

### `RESEARCH`
- Description: Multi-query search.
```text
query one
query two
  query three
```
"""

    # Act
    plan = parser.parse(plan_content)

    # Assert
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.type == "RESEARCH"

    # We expect individual lines to be treated as separate queries,
    # stripped of leading/trailing whitespace.
    expected_queries = ["query one", "query two", "query three"]
    assert action.params["queries"] == expected_queries
