from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple


class MarkdownPlanBuilder:
    """A fluent builder for creating Markdown plan strings for acceptance tests."""

    def __init__(self, title: str):
        """Initializes the builder with a plan title."""
        self._title = title
        self._actions: List[Dict[str, Any]] = []

    def add_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        content_blocks: Optional[Dict[str, Tuple[str, str]]] = None,
    ):
        """Adds an action block to the plan and returns self for chaining."""
        self._actions.append(
            {
                "type": action_type,
                "params": params,
                "content_blocks": content_blocks,
            }
        )
        return self

    def build(self) -> str:
        """Builds and returns the final Markdown plan string."""
        header = dedent(
            f"""\
            # {self._title}
            - **Status:** Green 🟢
            - **Plan Type:** Implementation
            - **Agent:** Developer
            """
        )

        rationale = dedent(
            """\
            ## Rationale
            ````text
            ### 1. Synthesis
            This is a test plan.

            ### 2. Justification
            This plan is for testing purposes.

            ### 3. Expected Outcome
            The test should pass.

            ### 4. State Dashboard
            **Vertical Slice:** `docs/slices/test.md`
            **Development Workflow:**
            - [ ] Phase 1
            **Active Phase Details:**
            *   **Test**
            **Architectural Notes:**
            - None
            ````
            """
        )

        action_plan_parts = ["## Action Plan"]
        if self._actions:
            for action in self._actions:
                action_type_upper = action["type"].upper()
                action_str = f"\n### `{action_type_upper}`"
                for key, value in action["params"].items():
                    action_str += f"\n- **{key}:** {value}"

                if action.get("content_blocks"):
                    block_parts = []
                    for key, (lang, content) in action["content_blocks"].items():
                        block = dedent(
                            f"""
                            #### {key}
                            `````{lang}
                            {content}
                            `````"""
                        )
                        block_parts.append(block.strip())
                    action_str += "\n\n" + "\n".join(block_parts)

                action_plan_parts.append(action_str)

        action_plan_section = "\n".join(action_plan_parts)

        return (
            f"{header.strip()}\n\n{rationale.strip()}\n\n{action_plan_section.strip()}"
        )
