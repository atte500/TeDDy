from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple, Union


class MarkdownPlanBuilder:
    """
    A fluent builder for creating Markdown plan strings for acceptance tests.
    Adheres to the TeDDy protocol defined in docs/project/specs/plan-format.md.
    """

    def __init__(self, title: str):
        """Initializes the builder with a plan title."""
        self._title = title
        self._actions: List[Dict[str, Any]] = []

    def _path_link(self, path: str) -> str:
        """Formats a path as a root-relative Markdown link."""
        return f"[{path}](/{path})"

    def add_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        content_blocks: Optional[Dict[str, Tuple[str, str]]] = None,
    ):
        """Legacy generic method for adding an action block."""
        self._actions.append(
            {
                "type": action_type,
                "params": params,
                "content_blocks": content_blocks,
            }
        )
        return self

    def add_create(
        self,
        path: str,
        content: str,
        overwrite: bool = False,
        description: str = "Creating file",
    ):
        params = {"File Path": self._path_link(path), "Description": description}
        if overwrite:
            params["Overwrite"] = "true"
        return self.add_action("CREATE", params, {"": ("text", content)})

    def add_read(self, resource: str, description: str = "Reading resource"):
        params = {"Resource": self._path_link(resource), "Description": description}
        return self.add_action("READ", params)

    def add_edit(
        self,
        path: str,
        find_replace: Union[str, List[Tuple[str, str]]],
        replace: Optional[str] = None,
        description: str = "Editing file",
        replace_all: bool = False,
    ):
        params = {"File Path": self._path_link(path), "Description": description}
        if replace_all:
            params["Replace All"] = "true"

        content_blocks = {}
        if isinstance(find_replace, list):
            for i, (f, r) in enumerate(find_replace):
                # Unique keys for multiple blocks
                content_blocks[f"FIND:_{i}"] = ("text", f)
                content_blocks[f"REPLACE:_{i}"] = ("text", r)
        else:
            content_blocks = {
                "FIND:": ("text", find_replace),
                "REPLACE:": ("text", replace or ""),
            }

        return self.add_action("EDIT", params, content_blocks)

    def add_execute(self, command: str, description: str = "Running command", **kwargs):
        """
        Adds an EXECUTE action. Supports expected_outcome, allow_failure,
        background, and timeout via kwargs.
        """
        params = {
            "Description": description,
            "Expected Outcome": kwargs.get("expected_outcome", "Success"),
        }
        if kwargs.get("allow_failure"):
            params["Allow Failure"] = "`true`"
        if kwargs.get("background"):
            params["Background"] = "`true`"
        if timeout := kwargs.get("timeout"):
            params["Timeout"] = str(timeout)

        return self.add_action("EXECUTE", params, {"": ("shell", command)})

    def add_research(self, queries: List[str], description: str = "Searching web"):
        content_blocks = {"": ("text", "\n".join(queries))}
        return self.add_action("RESEARCH", {"Description": description}, content_blocks)

    def add_prompt(self, message: str, reference_files: Optional[List[str]] = None):
        params = {"prompt": message}
        if reference_files:
            params["Reference Files"] = "\n".join(
                self._path_link(f) for f in reference_files
            )
        return self.add_action("PROMPT", params)

    def add_invoke(
        self, agent: str, description: str, reference_files: Optional[List[str]] = None
    ):
        params = {"Agent": agent, "Description": description}
        if reference_files:
            params["Reference Files"] = "\n".join(
                self._path_link(f) for f in reference_files
            )
        return self.add_action("INVOKE", params)

    def add_return(self, description: str, reference_files: Optional[List[str]] = None):
        params = {"Description": description}
        if reference_files:
            params["Reference Files"] = "\n".join(
                self._path_link(f) for f in reference_files
            )
        return self.add_action("RETURN", params)

    def add_prune(self, resource: str, description: str = "Pruning resource"):
        params = {"File Path": self._path_link(resource), "Description": description}
        return self.add_action("PRUNE", params)

    def _render_params(self, params: Dict[str, Any]) -> str:
        lines = []
        params_copy = params.copy()
        for key, value in params_copy.items():
            if key in ["command", "prompt"]:
                continue
            lines.append(f"- **{key}:** {value}")
        return "\n" + "\n".join(lines) if lines else ""

    def _render_content_blocks(
        self, action_type: str, content_blocks: Optional[Dict[str, Tuple[str, str]]]
    ) -> str:
        if not content_blocks:
            return ""
        parts = []
        for key, (lang, content) in content_blocks.items():
            # Strip suffix from unique keys used for multi-edit
            display_key = key.split("_")[0] if "_" in key else key
            key_str = (
                f"#### {display_key}" if display_key and action_type == "EDIT" else ""
            )

            fence = "`````"
            if action_type in ["CREATE", "EXECUTE", "RESEARCH"]:
                fence = "````"

            block = (
                f"{key_str}\n{fence}{lang}\n{content}\n{fence}"
                if key_str
                else f"{fence}{lang}\n{content}\n{fence}"
            )
            parts.append(block)
        return "\n\n" + "\n".join(parts)

    def _build_action(self, action: Dict[str, Any]) -> str:
        action_type = action["type"].upper()
        params = action.get("params", {})
        content_blocks = action.get("content_blocks")

        action_str = f"\n### `{action_type}`"
        action_str += self._render_params(params)

        if action_type == "PROMPT":
            action_str += f"\n\n{params.get('prompt', '')}"
        elif action_type == "EXECUTE":
            command = params.get("command")
            if not command and content_blocks:
                if "COMMAND" in content_blocks:
                    command = content_blocks["COMMAND"][1]
                else:
                    command = content_blocks.get("", ("", ""))[1]

            if command:
                action_str += f"\n\n````shell\n{command}\n````"
        else:
            action_str += self._render_content_blocks(action_type, content_blocks)

        return action_str

    def build(self) -> str:
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
        for action in self._actions:
            action_plan_parts.append(self._build_action(action))

        return (
            f"{header.strip()}\n\n{rationale.strip()}\n\n"
            + "\n".join(action_plan_parts).strip()
        )
