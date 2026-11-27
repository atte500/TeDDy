"""MRE: seed the shared litellm counter before the wiring test runs.
The wiring test asserts an absolute ``litellm.completion.call_count == 2``
against the process-global Mock installed by tests/harness/setup/composition.py.
List-valued ``side_effect`` entries are consumed independently of ``call_count``,
so prior calls inflate the counter without disturbing the scripted attempts.
This plugin reproduces the CI observation (5 instead of 2) by recording three
calls before the test body executes.
"""
import sys
TARGET = "test_validation_then_retry_wiring"
PRIOR_CALLS = 3
_state = {"seeded": False}
def pytest_runtest_setup(item):
    if _state["seeded"] or TARGET not in item.nodeid:
        return
    litellm = sys.modules.get("litellm")
    if litellm is None:
        return
    for index in range(PRIOR_CALLS):
        litellm.completion(messages=[{"role": "user", "content": f"prior-{index}"}])
    _state["seeded"] = True
    print(
        f"\nSEEDED {PRIOR_CALLS} prior calls, call_count={litellm.completion.call_count}",
        flush=True,
    )
