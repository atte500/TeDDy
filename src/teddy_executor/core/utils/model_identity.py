"""Model identity presentation shared by the reviewer's Context panel."""

from typing import Optional


UNKNOWN_MODEL_NAME = "Unknown"
UNKNOWN_PROVIDER = "unknown"


def split_model_identity(model: Optional[str]) -> tuple[str, str]:
    """Split a LiteLLM model string into its display name and provider.

    A model string is ``provider/model``, where the provider segment is
    optional, so the provider is a pure function of the name. A provider-less
    model reports ``unknown`` rather than inventing one, and an unresolved model
    reports the placeholders the panel renders instead of an empty cell.
    """
    name = (str(model).strip() if model else "") or UNKNOWN_MODEL_NAME
    if name == UNKNOWN_MODEL_NAME:
        return UNKNOWN_MODEL_NAME, UNKNOWN_PROVIDER

    provider, separator, remainder = name.partition("/")
    if not separator or not provider or not remainder:
        return name, UNKNOWN_PROVIDER

    return remainder, provider
