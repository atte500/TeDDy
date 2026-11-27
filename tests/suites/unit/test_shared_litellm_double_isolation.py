"""Unit tests for the seam that isolates the process-global litellm double.

The harness installs one Mock as ``sys.modules["litellm"]`` for the whole
session, so its call history and scripted behaviour belong to the process
rather than to a single test. An absolute ``litellm.completion.call_count``
assertion read from it is only truthful when every test starts clean.
"""

from unittest.mock import Mock

import litellm
import pytest

from tests.harness.setup.composition import reset_shared_litellm_double


def test_reset_clears_call_history_and_scripted_side_effect():
    """A scripted failure must not survive into the next test."""
    litellm.completion.side_effect = [RuntimeError("transient outage")]
    with pytest.raises(RuntimeError):
        litellm.completion(messages=[{"role": "user", "content": "seed"}])
    assert litellm.completion.call_count == 1

    reset_shared_litellm_double()

    assert litellm.completion.call_count == 0
    assert litellm.completion.side_effect is None


def test_reset_restores_the_safe_by_default_response():
    """A swapped return value must not survive into the next test."""
    litellm.completion.return_value = Mock()

    reset_shared_litellm_double()

    response = litellm.completion(messages=[{"role": "user", "content": "hello"}])

    assert "Mock Plan" in response.choices[0].message.content


def test_every_test_starts_with_a_clean_completion_double():
    """The autouse fixture guarantees a clean double before each test body."""
    assert litellm.completion.call_count == 0
    assert litellm.completion.side_effect is None
