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

    def _render_params(self, params: Dict[str, Any]) -> str:
        """Renders the key-value parameters for an action."""
        lines = []
        # Use .copy() to avoid modifying the original dict during iteration
        params_copy = params.copy()
        env_val = params_copy.pop("env", None)
        for key, value in params_copy.items():
            # These are handled by their specific action formatters
            if key in ["command", "Handoff Message", "prompt"]:
                continue
            lines.append(f"- **{key}:** {value}")
        if env_val:
            lines.append(f"- **env:**\n  {env_val}")
        return "\n" + "\n".join(lines) if lines else ""

    def _render_content_blocks(
        self, action_type: str, content_blocks: Optional[Dict[str, Tuple[str, str]]]
    ) -> str:
        """Renders code blocks like FIND/REPLACE or file content."""
        if not content_blocks:
            return ""
        parts = []
        for key, (lang, content) in content_blocks.items():
            key_str = f"#### {key}" if key and action_type == "EDIT" else ""
            fence = "````" if action_type == "CREATE" else "`````"
            block = (
                f"{key_str}\n{fence}{lang}\n{content}\n{fence}"
                if key_str
                else f"{fence}{lang}\n{content}\n{fence}"
            )
            parts.append(block)
        return "\n\n" + "\n".join(parts)

    def _build_action(self, action: Dict[str, Any]) -> str:
        """Builds the string for a single action."""
        action_type = action["type"].upper()
        params = action.get("params", {})
        content_blocks = action.get("content_blocks")

        action_str = f"\n### `{action_type}`"
        action_str += self._render_params(params)

        if action_type == "CHAT_WITH_USER":
            action_str += f"\n\n{params.get('prompt', '')}"
        elif action_type == "EXECUTE":
            command = (
                params.get("command")
                or (content_blocks or {}).get("COMMAND", ("", ""))[1]
            )
            if command:
                action_str += f"\n\n````shell\n{command}\n````"
        elif action_type == "INVOKE":
            if handoff_message := params.get("Handoff Message"):
                action_str += f"\n\n{handoff_message}"
        else:
            action_str += self._render_content_blocks(action_type, content_blocks)

        return action_str

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
                action_plan_parts.append(self._build_action(action))

        action_plan_section = "\n".join(action_plan_parts)

        return (
            f"{header.strip()}\n\n{rationale.strip()}\n\n{action_plan_section.strip()}"
        )
