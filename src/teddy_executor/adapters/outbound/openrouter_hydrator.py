import re
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional
from teddy_executor.adapters.outbound.litellm_adapter import IOpenRouterHydrator
from teddy_executor.core.ports.outbound import IConfigService


class OpenRouterMetadataHydrator(IOpenRouterHydrator):
    """
    Fetches and caches model metadata from the OpenRouter API.
    Supports suffix-stripping for versioned models.
    """

    API_URL = "https://openrouter.ai/api/v1/models"
    TIMEOUT = 10.0
    CACHE_PATH = Path(".teddy/.model_registry_cache.json")

    def __init__(
        self,
        cache_path: Optional[Path] = None,
        config_service: Optional[IConfigService] = None,
    ) -> None:
        self._cached_models: Optional[List[Dict[str, Any]]] = None
        self.cache_path = cache_path
        self.config_service = config_service

    def _fetch_models(self) -> List[Dict[str, Any]]:
        """Fetches the live catalog from OpenRouter with a timeout."""
        if self._cached_models is not None:
            return self._cached_models

        try:
            response = requests.get(self.API_URL, timeout=self.TIMEOUT)
            response.raise_for_status()
            data = response.json()
            self._cached_models = data.get("data", [])
            return self._cached_models or []
        except (requests.RequestException, ValueError):
            return []

    def get_metadata(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns metadata for a model, stripping suffixes if necessary.
        """
        models = self._fetch_models()
        if not models:
            return None

        # Strip openrouter/ prefix if present to match catalog IDs
        clean_id = model_id.removeprefix("openrouter/")

        # Strip colon-based routing shortcuts (e.g., :nitro, :floor)
        # OpenRouter appends these to route requests; they must be removed before ID lookup.
        clean_id = re.sub(r":[^/:]+$", "", clean_id)

        # 1. Try exact match
        metadata = self._find_model(models, clean_id)
        if metadata:
            return metadata

        # 2. Try suffix stripping (e.g. -20240525)
        # Matches patterns like -20240525 or -202405251230
        stripped_id = re.sub(r"-\d{8,12}$", "", clean_id)
        if stripped_id != clean_id:
            metadata = self._find_model(models, stripped_id)
            if metadata:
                return metadata

        return None

    def _find_model(
        self, models: List[Dict[str, Any]], model_id: str
    ) -> Optional[Dict[str, Any]]:
        """Helper to find a model in the list and format the result."""
        for m in models:
            if m.get("id") == model_id:
                pricing = m.get("pricing", {})
                try:
                    input_cost = float(pricing.get("prompt", 0))
                    output_cost = float(pricing.get("completion", 0))
                except (ValueError, TypeError):
                    return None
                return {
                    "context_window": m.get("context_length", 0),
                    "pricing": {
                        "input_cost_per_token": input_cost,
                        "output_cost_per_token": output_cost,
                    },
                }
        return None
