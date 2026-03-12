from pathlib import Path
from typing import Any, Dict, Optional, Sequence, cast
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient


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
    ):
        self._context_service = context_service
        self._llm_client = llm_client
        self._file_system_manager = file_system_manager
        self._config_service = config_service

    def generate_plan(
        self,
        user_message: str,
        turn_dir: str,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
    ) -> str:
        import yaml
        import json

        turn_path = Path(turn_dir)

        # 1. Gather context
        context = self._context_service.get_context(context_files=context_files)

        # 2. Fetch system prompt
        # Read meta.yaml to find the agent name
        meta_file_path = (turn_path / "meta.yaml").as_posix()
        meta_content = ""
        if self._file_system_manager.path_exists(meta_file_path):
            meta_content = self._file_system_manager.read_file(meta_file_path)

        # Defensive: cast content to str to prevent yaml.safe_load hanging on MagicMocks
        meta = cast(Dict[str, Any], yaml.safe_load(str(meta_content)) or {})
        agent_name = meta.get("agent_name", "pathfinder")

        prompt_file_path = (turn_path / f"{agent_name}.xml").as_posix()
        system_prompt = ""
        if self._file_system_manager.path_exists(prompt_file_path):
            system_prompt = self._file_system_manager.read_file(prompt_file_path)

        # 3. Inject Contextual Hints
        # Session Start: If turn 01, encourage alignment
        if turn_path.name == "01":
            hint = "\n\n*(Hint: first make sure you are aligned with the user's intentions and have the full context required)*"
            user_message += hint

        # 4. Call LLM
        # Combine header and content for the LLM
        full_context = f"{context.header}\n{context.content}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{full_context}\n\nUser Message: {user_message}",
            },
        ]

        # Log exact raw payload
        log_path = (turn_path / "input.log").as_posix()
        self._file_system_manager.write_file(
            log_path, json.dumps(messages, indent=2, ensure_ascii=False)
        )

        # Resolve model from config with fallback
        model = self._config_service.get_setting("planning_model", "gpt-4o") or "gpt-4o"

        # Call LLM and gather telemetry
        token_count = self._llm_client.get_token_count(model, messages)
        response = self._llm_client.get_completion(model=model, messages=messages)
        plan_content = self._extract_plan_content(response)
        turn_cost = self._llm_client.get_completion_cost(response)

        # 5. Persistence
        plan_path = (turn_path / "plan.md").as_posix()
        self._file_system_manager.write_file(plan_path, plan_content)

        # 6. Update meta.yaml
        self._update_meta(meta, response, token_count, turn_cost, meta_file_path)

        return plan_path

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

        # Defensive Cleanup: Ensure all metadata is a primitive type (str, int, float, bool)
        # to prevent yaml.dump from hanging on MagicMocks during unit tests.
        serializable_meta = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)) and not hasattr(
                v, "_mock_return_value"
            ):
                serializable_meta[k] = v
            else:
                serializable_meta[k] = str(v)

        self._file_system_manager.write_file(
            meta_file_path, yaml.dump(serializable_meta)
        )
