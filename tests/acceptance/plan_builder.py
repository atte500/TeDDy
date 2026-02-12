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
                params = action["params"]
                content_blocks = action.get("content_blocks") or {}

                if action_type_upper == "CHAT_WITH_USER":
                    prompt = params.get("prompt")
                    if prompt:
                        action_str += f"\n\n{prompt}"
                    action_plan_parts.append(action_str)
                    continue

                # Pop special-handled keys from params to avoid double-printing
                command = params.pop("command", None)
                handoff_message = params.pop("Handoff Message", None)
                env_val = params.pop("env", None)

                # Render all remaining standard parameters
                for key, value in params.items():
                    action_str += f"\n- **{key}:** {value}"

                # Render special nested list for env if it exists
                if env_val:
                    action_str += f"\n- **env:**\n  {env_val}"

                # Action-specific content block rendering
                if action_type_upper == "EXECUTE":
                    # Command can come from params or content_blocks
                    command_content = command
                    if not command_content:
                        # Check both `COMMAND` and `` `COMMAND:` `` for compatibility
                        command_block = content_blocks.get(
                            "COMMAND"
                        ) or content_blocks.get("`COMMAND:`")
                        if command_block:
                            _, command_content = command_block

                    if command_content:
                        action_str += f"\n\n````shell\n{command_content}\n````"

                elif action_type_upper == "INVOKE":
                    if handoff_message:
                        action_str += f"\n\n{handoff_message}"

                else:  # Generic handling for CREATE, EDIT
                    if content_blocks:
                        block_parts = []
                        for key, (lang, content) in content_blocks.items():
                            key_str = f"#### {key}" if key else ""
                            fence_str = f"`````{lang}\n{content}\n`````"
                            block = f"{key_str}\n{fence_str}" if key else fence_str
                            block_parts.append(block)

                        # Join with a single newline. The test expects no blank line between blocks.
                        action_str += "\n\n" + "\n".join(block_parts)

                action_plan_parts.append(action_str)

        action_plan_section = "\n".join(action_plan_parts)

        return (
            f"{header.strip()}\n\n{rationale.strip()}\n\n{action_plan_section.strip()}"
        )
