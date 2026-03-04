from typing import Any, Dict, List
import litellm
from teddy_executor.core.ports.outbound.llm_client import ILlmClient, LlmApiError


class LiteLLMAdapter(ILlmClient):
    """
    Implements ILlmClient using the litellm library.
    """

    def get_completion(
        self, model: str, messages: List[Dict[str, str]], **kwargs: Any
    ) -> str:
        """
        Sends a request to an LLM via litellm and returns the text response.
        """
        try:
            response = litellm.completion(model=model, messages=messages, **kwargs)
            # litellm returns a response object with choices
            if hasattr(response, "choices") and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            return ""
        except Exception as e:
            # Wrap all litellm exceptions in our domain exception
            raise LlmApiError(f"LLM Completion failed: {str(e)}") from e
