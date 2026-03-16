from textwrap import dedent
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


def test_parse_edit_with_threshold():
    parser = MarkdownPlanParser()
    plan = dedent("""\
        # Plan
        - Status: Green 🟢
        - Agent: Developer
        - Plan Type: Implementation

        ## Rationale
        ```text
        ### 1. Synthesis
        ...
        ### 2. Justification
        ...
        ### 3. Expected Outcome
        ...
        ### 4. State Dashboard
        ...
        ```

        ## Action Plan
        ### `EDIT`
        - File Path: [app.py](/app.py)
        - Similarity Threshold: 0.95
        - Description: Custom threshold.

        #### `FIND:`
        ```python
        old
        ```
        #### `REPLACE:`
        ```python
        new
        ```
        """)
    parsed_plan = parser.parse(plan)
    action = parsed_plan.actions[0]

    assert action.type == "EDIT"
    expected_threshold = 0.95
    assert action.params["similarity_threshold"] == expected_threshold


def test_parse_edit_without_threshold_defaults_to_none():
    parser = MarkdownPlanParser()
    plan = dedent("""\
        # Plan
        - Status: Green 🟢
        - Agent: Developer
        - Plan Type: Implementation

        ## Rationale
        ```text
        ### 1. Synthesis
        ...
        ### 2. Justification
        ...
        ### 3. Expected Outcome
        ...
        ### 4. State Dashboard
        ...
        ```

        ## Action Plan
        ### `EDIT`
        - File Path: [app.py](/app.py)
        - Description: Default threshold.

        #### `FIND:`
        ```python
        old
        ```
        #### `REPLACE:`
        ```python
        new
        ```
        """)
    parsed_plan = parser.parse(plan)
    action = parsed_plan.actions[0]

    assert action.type == "EDIT"
    assert "similarity_threshold" not in action.params
