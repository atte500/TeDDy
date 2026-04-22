from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase


class PlanningService(IPlanningUseCase):
    """
    Orchestrates context gathering and LLM interaction to generate plans.
    """

    from teddy_executor.core.domain.models.planning_ports import PlanningPorts

    def __init__(self, ports: PlanningPorts):
        self._context_service = ports.context
        self._llm_client = ports.llm
        self._file_system_manager = ports.fs
        self._config_service = ports.config
        self._prompt_manager = ports.prompts
        self._user_interactor = ports.ui

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
        resolved_message = await self._prompt_manager.async_resolve_message(
            user_message, turn_path
        )

        agent_name, meta, meta_file_path = await anyio.to_thread.run_sync(
            self._prompt_manager.resolve_agent_metadata, turn_path
        )

        if self._user_interactor:
            session_folder = turn_path.parent.name
            natural_name = re.sub(r"^\d{8}_\d{6}-", "", session_folder)
            msg = f"[cyan][{turn_path.name}] {natural_name} | Waiting for {agent_name} to respond...[/cyan]"
            await self._user_interactor.async_display_message(msg)

        context = await self._context_service.async_get_context(
            context_files=context_files
        )
        system_prompt = await self._prompt_manager.async_fetch_system_prompt(
            agent_name, turn_path
        )

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

        cost_val = await self._prompt_manager.async_log_telemetry(
            token_count, turn_cost
        )
        plan_path = (turn_path / "plan.md").as_posix()
        await anyio.to_thread.run_sync(
            self._file_system_manager.write_file, plan_path, plan_content
        )
        await anyio.to_thread.run_sync(
            self._prompt_manager.update_meta,
            meta,
            response,
            token_count,
            turn_cost,
            meta_file_path,
        )

        return plan_path, cost_val

    def generate_plan(
        self,
        user_message: Optional[str],
        turn_dir: str,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
    ) -> tuple[str, float]:
        """Generates a new plan.md file."""
        turn_path = Path(turn_dir)
        resolved_message = self._prompt_manager.resolve_message(user_message, turn_path)

        if resolved_message is None:
            return None, 0.0  # type: ignore

        context = self._context_service.get_context(context_files=context_files)
        agent_name, meta, meta_file_path = self._prompt_manager.resolve_agent_metadata(
            turn_path
        )

        system_prompt = self._prompt_manager.fetch_system_prompt(agent_name, turn_path)

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

        cost_val = self._prompt_manager.log_telemetry(token_count, turn_cost)
        plan_path = (turn_path / "plan.md").as_posix()
        self._file_system_manager.write_file(plan_path, plan_content)
        self._prompt_manager.update_meta(
            meta, response, token_count, turn_cost, meta_file_path
        )

        return plan_path, cost_val

    def _extract_plan_content(self, response: Any) -> str:
        """Robustly extracts content from the LLM response object."""
        if hasattr(response, "choices") and len(response.choices) > 0:
            return getattr(response.choices[0].message, "content", "") or ""
        return ""
