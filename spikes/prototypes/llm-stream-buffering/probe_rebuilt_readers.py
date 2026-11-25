"""Probe: does a rebuilt ModelResponse satisfy the adapter's existing readers?"""

import litellm

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


class StubConfig:
    """Minimal IConfigService stand-in: the probe needs no file or env access."""

    def __init__(self, settings):
        self._settings = settings

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)


MESSAGES = [{"role": "user", "content": "say hello"}]


def build_streamed_response(stream_options):
    request = {
        "model": "gpt-4o",
        "messages": MESSAGES,
        "mock_response": "hello world",
        "stream": True,
    }
    if stream_options is not None:
        request["stream_options"] = stream_options
    wrapper = litellm.completion(**request)
    chunks = list(wrapper)
    return litellm.stream_chunk_builder(chunks, messages=MESSAGES)


def main():
    adapter = LiteLLMAdapter(
        config_service=StubConfig({"llm.model": "gpt-4o", "llm.api_key": "sk-test"})
    )

    for label, options in (("with include_usage", {"include_usage": True}), ("without", None)):
        built = build_streamed_response(options)
        print(f"\n== rebuilt response {label} ==")
        if built is None:
            print("  builder returned None")
            continue
        print(f"  has choices: {hasattr(built, 'choices')}")
        print(f"  content: {built.choices[0].message.content!r}")
        print(f"  finish_reason: {getattr(built.choices[0], 'finish_reason', None)!r}")
        print(f"  adapter.get_token_usage: {adapter.get_token_usage(built)!r}")
        print(f"  adapter.get_completion_cost: {adapter.get_completion_cost(built, model_override='gpt-4o')!r}")
        print(f"  _teddy_cost_recorded: {getattr(built, '_teddy_cost_recorded', None)!r}")


main()
