from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SessionOptions:
    """
    Options for initializing a new session.
    """

    name: str
    agent_name: str
    initial_request: Optional[str] = None
    additional_context: list[str] = field(default_factory=list)
    model: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
