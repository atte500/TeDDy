from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    """Provider-reported token usage for one completion.

    ``prompt_tokens`` is the provider's own input count, not the request
    estimate the client computes before the call. ``cached_tokens`` is the
    portion the provider served from its prompt cache. Absent provider data is
    reported as ``0``, never as a guess.
    """

    prompt_tokens: int = 0
    cached_tokens: int = 0
