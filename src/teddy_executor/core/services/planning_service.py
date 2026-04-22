from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


class PlanningService(IPlanningUseCase):
    """
    Orchestrates context gathering and LLM interaction to generate plans.
    """

    def __init__(
        self,
        context_service: IGetContextUseCase,
        llm_client: ILlmClient,
        file_system_manager: IFileSystemManager,
        config_service: IConfigService,
        user_interactor: IUserInteractor = None,  # type: ignore
    ):
        self._context_service = context_service
        self._llm_client = llm_client
        self._file_system_manager = file_system_manager
        self._config_service = config_service
        self._user_interactor = user_interactor

    def _resolve_agent_metadata(
        self, turn_path: Path
    ) -> tuple[str, Dict[str, Any], str]:
        """Resolves agent name and metadata from meta.yaml."""
        import yaml

        meta_file_path = (turn_path / "meta.yaml").as_posix()
        meta_content = ""
        if self._file_system_manager.path_exists(meta_file_path):
            meta_content = self._file_system_manager.read_file(meta_file_path)

        meta = yaml.safe_load(str(meta_content))
        if not isinstance(meta, dict):
            meta = {}
        return meta.get("agent_name", "pathfinder"), meta, meta_file_path

    def _ensure_alignment_hint(
        self, message: str, default: Optional[str] = None
    ) -> str:
        """Appends the alignment hint or returns a default if empty."""
        if not message or not message.strip():
            return default or ""

        hint = "\n\n*(Stop to reply to this user request and ensure alignment before proceeding)*"
        if hint not in message and "(No instructions provided" not in message:
            return message + hint
        return message

    async def _async_resolve_message(
        self, user_message: Optional[str], turn_path: Path
    ) -> str:
        """Asynchronously resolves the user message."""
        import anyio
        from teddy_executor.core.utils.markdown import extract_markdown_section

        resolved = user_message
        if not resolved:
            report_path = (turn_path / "report.md").as_posix()
            if await anyio.to_thread.run_sync(
                self._file_system_manager.path_exists, report_path
            ):
                report_content = await anyio.to_thread.run_sync(
                    self._file_system_manager.read_file, report_path
                )
                resolved = extract_markdown_section(report_content, "User Request")

        if not resolved and self._user_interactor:
            resolved = await self._user_interactor.async_ask_question(
                "Enter your instructions for the AI"
            )

        default = "(No instructions provided; proceeding with current context as primary instruction)"
        return self._ensure_alignment_hint(resolved or "", default=default)

    async def _async_fetch_system_prompt(self, agent_name: str, turn_path: Path) -> str:
        """Asynchronously fetches the system prompt."""
        import anyio

        prompt_file_path = (turn_path / f"{agent_name}.xml").as_posix()
        if await anyio.to_thread.run_sync(
            self._file_system_manager.path_exists, prompt_file_path
        ):
            return await anyio.to_thread.run_sync(
                self._file_system_manager.read_file, prompt_file_path
            )
        return ""

    async def async_generate_plan(
        self,
        user_message: Optional[str],
        turn_dir: str,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
    ) -> tuple[str, float]:
        """Asynchronously generates a new plan.md file."""
        import anyio
        import re

        turn_path = Path(turn_dir)
        resolved_message = await self._async_resolve_message(user_message, turn_path)

        agent_name, meta, meta_file_path = await anyio.to_thread.run_sync(
            self._resolve_agent_metadata, turn_path
        )

        if self._user_interactor:
            session_folder = turn_path.parent.name
            natural_name = re.sub(r"^\d{8}_\d{6}-", "", session_folder)
            msg = f"[cyan][{turn_path.name}] {natural_name} | Waiting for {agent_name} to respond...[/cyan]"
            await self._user_interactor.async_display_message(msg)

        context = await self._context_service.async_get_context(
            context_files=context_files
        )
        system_prompt = await self._async_fetch_system_prompt(agent_name, turn_path)

        full_context = f"{context.header}\n{context.content}"
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{full_context}\n\nUser Message: {resolved_message}",
            },
        ]

        await anyio.to_thread.run_sync(
            self._file_system_manager.write_file,
            (turn_path / "input.md").as_posix(),
            full_context,
        )

        model = self._config_service.get_setting("planning_model", "gpt-4o") or "gpt-4o"
        token_count = self._llm_client.get_token_count(model, messages)
        response = await self._llm_client.async_get_completion(
            model=model, messages=messages
        )
        plan_content = self._extract_plan_content(response)
        turn_cost = self._llm_client.get_completion_cost(response)

        cost_val = await self._async_log_telemetry(token_count, turn_cost)
        plan_path = (turn_path / "plan.md").as_posix()
        await anyio.to_thread.run_sync(
            self._file_system_manager.write_file, plan_path, plan_content
        )
        await anyio.to_thread.run_sync(
            self._update_meta, meta, response, token_count, turn_cost, meta_file_path
        )

        return plan_path, cost_val

    async def _async_log_telemetry(self, token_count: Any, turn_cost: Any) -> float:
        """Logs planning telemetry asynchronously."""

        def safe_float(v: Any, default: float = 0.0) -> float:
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        cost_val = safe_float(turn_cost)
        count_val = int(safe_float(token_count))
        msg_tokens, msg_cost = f"Tokens: {count_val}", f"Cost: ${cost_val:.4f}"

        if self._user_interactor:
            await self._user_interactor.async_display_message(msg_tokens)
            await self._user_interactor.async_display_message(msg_cost)
        else:
            import sys

            sys.stdout.write(f"{msg_tokens}\n{msg_cost}\n")
            sys.stdout.flush()
        return cost_val

    def _resolve_message(
        self, user_message: Optional[str], turn_path: Path
    ) -> Optional[str]:
        """Synchronously resolves the user message."""
        from teddy_executor.core.utils.markdown import extract_markdown_section

        resolved = user_message

        if not resolved:
            report_path = (turn_path / "report.md").as_posix()
            if self._file_system_manager.path_exists(report_path):
                report_content = self._file_system_manager.read_file(report_path)
                resolved = extract_markdown_section(report_content, "User Request")

        if not resolved and self._user_interactor:
            resolved = self._user_interactor.ask_question(
                "Enter your instructions for the AI"
            )

        if not resolved or not resolved.strip():
            return None

        return self._ensure_alignment_hint(resolved)

    def generate_plan(
        self,
        user_message: Optional[str],
        turn_dir: str,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
    ) -> tuple[str, float]:
        """Generates a new plan.md file."""
        import os

        if os.getenv("TEDDY_SHOWCASE_MOCK_LLM") == "1":
            return self._handle_showcase_mock(user_message, turn_dir, context_files)

        turn_path = Path(turn_dir)
        resolved_message = self._resolve_message(user_message, turn_path)

        if resolved_message is None:
            return None, 0.0  # type: ignore

        context = self._context_service.get_context(context_files=context_files)
        agent_name, meta, meta_file_path = self._resolve_agent_metadata(turn_path)

        prompt_file_path = (turn_path / f"{agent_name}.xml").as_posix()
        system_prompt = ""
        if self._file_system_manager.path_exists(prompt_file_path):
            system_prompt = self._file_system_manager.read_file(prompt_file_path)

        full_context = f"{context.header}\n{context.content}"
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{full_context}\n\nUser Message: {resolved_message}",
            },
        ]

        self._file_system_manager.write_file(
            (turn_path / "input.md").as_posix(), full_context
        )
        model = self._config_service.get_setting("planning_model", "gpt-4o") or "gpt-4o"
        token_count = self._llm_client.get_token_count(model, messages)
        response = self._llm_client.get_completion(model=model, messages=messages)
        plan_content = self._extract_plan_content(response)
        turn_cost = self._llm_client.get_completion_cost(response)

        cost_val = self._log_telemetry(token_count, turn_cost)
        plan_path = (turn_path / "plan.md").as_posix()
        self._file_system_manager.write_file(plan_path, plan_content)
        self._update_meta(meta, response, token_count, turn_cost, meta_file_path)

        return plan_path, cost_val

    def _handle_showcase_mock(
        self,
        user_message: Optional[str],
        turn_dir: str,
        context_files: Optional[Dict[str, Sequence[str]]],
    ) -> tuple[str, float]:
        """Handles the TEDDY_SHOWCASE_MOCK_LLM recursion guard."""
        from prototypes.slice_00_05_logic import generate_plan_sequenced

        if not getattr(self, "_in_showcase_mock", False):
            self._in_showcase_mock = True
            try:
                return generate_plan_sequenced(
                    self,
                    self._user_interactor,
                    user_message,
                    turn_dir,
                    context_files,
                    "pathfinder",
                )
            finally:
                self._in_showcase_mock = False
        return "", 0.0

    def _log_telemetry(self, token_count: Any, turn_cost: Any) -> float:
        """Logs planning telemetry to the appropriate output stream."""

        def safe_float(v: Any, default: float = 0.0) -> float:
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        cost_val = safe_float(turn_cost)
        count_val = int(safe_float(token_count))
        msg_tokens, msg_cost = f"Tokens: {count_val}", f"Cost: ${cost_val:.4f}"

        if self._user_interactor:
            self._user_interactor.display_message(msg_tokens)
            self._user_interactor.display_message(msg_cost)
        else:
            import sys

            sys.stdout.write(f"{msg_tokens}\n{msg_cost}\n")
            sys.stdout.flush()
        return cost_val

    def _extract_plan_content(self, response: Any) -> str:
        """Robustly extracts content from the LLM response object."""
        if hasattr(response, "choices") and len(response.choices) > 0:
            return getattr(response.choices[0].message, "content", "") or ""
        return ""

    def _update_meta(
        self,
        meta: Dict[str, Any],
        response: Any,
        token_count: int,
        turn_cost: float,
        meta_file_path: str,
    ) -> None:
        """Updates and persists turn metadata with telemetry and cost info."""
        import yaml

        try:
            meta["turn_cost"] = float(turn_cost)
            meta["token_count"] = int(token_count)
        except (TypeError, ValueError):
            meta["turn_cost"] = meta.get("turn_cost", 0.0)
            meta["token_count"] = meta.get("token_count", 0)

        meta["model"] = str(getattr(response, "model", "unknown"))

        from teddy_executor.core.utils.serialization import scrub_dict_for_serialization

        serializable_meta = scrub_dict_for_serialization(meta)
        self._file_system_manager.write_file(
            meta_file_path, yaml.dump(serializable_meta)
        )
