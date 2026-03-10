import os
from typing import Dict, Optional, Sequence
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
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
    ):
        self._context_service = context_service
        self._llm_client = llm_client
        self._file_system_manager = file_system_manager

    def generate_plan(
        self,
        user_message: str,
        turn_dir: str,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
    ) -> str:
        # 1. Gather context
        context = self._context_service.get_context(context_files=context_files)

        # 2. Fetch system prompt
        prompt_path = os.path.join(turn_dir, "system_prompt.xml")
        system_prompt = self._file_system_manager.read_file(prompt_path)

        # 3. Inject Contextual Hints
        # Session Start: If turn 01, encourage alignment
        if os.path.basename(turn_dir) == "01":
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

        plan_content = self._llm_client.get_completion(
            model="gpt-4o",  # Default model, should eventually come from config
            messages=messages,
        )

        # 4. Persistence
        plan_path = os.path.join(turn_dir, "plan.md")
        self._file_system_manager.write_file(plan_path, plan_content)

        return plan_path
