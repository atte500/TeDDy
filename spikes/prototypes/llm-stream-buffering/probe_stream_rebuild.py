"""Probe: what does litellm return under stream=True, and can chunks be rebuilt
into a response the existing adapter and planning readers accept unchanged?"""

import importlib.metadata as md

import litellm

MESSAGES = [{"role": "user", "content": "say hello"}]


def describe(label, value):
    print(f"  {label}: {value!r}")


def probe_streamed_call(stream_options=None):
    header = "== stream=True"
    if stream_options:
        header += f", stream_options={stream_options}"
    print(f"\n{header} ==")
    kwargs = {"model": "gpt-4o", "messages": MESSAGES, "mock_response": "hello world", "stream": True}
    if stream_options:
        kwargs["stream_options"] = stream_options
    resp = litellm.completion(**kwargs)
    describe("type", type(resp).__name__)

    print("  -- what the current callers would see BEFORE consuming --")
    try:
        choices = resp.choices
        describe("choices len", len(choices))
        if choices:
            describe("choices[0].message.content", getattr(choices[0].message, "content", None))
            describe("choices[0].finish_reason", getattr(choices[0], "finish_reason", None))
    except Exception as exc:
        print(f"  choices access raised: {type(exc).__name__}: {exc}")
    describe("usage", getattr(resp, "usage", None))

    print("  -- consuming the stream --")
    chunks = list(resp)
    describe("chunk count", len(chunks))
    describe("first chunk type", type(chunks[0]).__name__)
    first = chunks[0]
    describe("first chunk text", first.choices[0].delta.content if first.choices else None)
    describe("first chunk usage", getattr(first, "usage", None))
    describe("last chunk usage", getattr(chunks[-1], "usage", None))

    print("  -- rebuild --")
    built = litellm.stream_chunk_builder(chunks, messages=MESSAGES)
    describe("built type", type(built).__name__ if built is not None else None)
    if built is None:
        return
    describe("built content", built.choices[0].message.content if built.choices else None)
    describe("built finish_reason", getattr(built.choices[0], "finish_reason", None) if built.choices else None)
    describe("built model", getattr(built, "model", None))
    usage = getattr(built, "usage", None)
    describe("built usage", usage)
    describe("built prompt_tokens", getattr(usage, "prompt_tokens", None) if usage else None)
    details = getattr(usage, "prompt_tokens_details", None) if usage else None
    describe("built cached_tokens", getattr(details, "cached_tokens", None) if details else None)
    describe("built _hidden_params", getattr(built, "_hidden_params", None))
    try:
        describe("completion_cost", litellm.completion_cost(completion_response=built))
    except Exception as exc:
        print(f"  completion_cost raised: {type(exc).__name__}: {exc}")


print("litellm version:", md.version("litellm"))
probe_streamed_call()
probe_streamed_call({"include_usage": True})

print("\n== stream_chunk_builder without messages= ==")
resp = litellm.completion(
    model="gpt-4o", messages=MESSAGES, mock_response="hello world", stream=True,
    stream_options={"include_usage": True},
)
chunks = list(resp)
try:
    built = litellm.stream_chunk_builder(chunks)
    print("  built without messages:", "ok" if built is not None else "None")
    if built is not None:
        describe("content", built.choices[0].message.content if built.choices else None)
        describe("usage", getattr(built, "usage", None))
except Exception as exc:
    print(f"  raised: {type(exc).__name__}: {exc}")
