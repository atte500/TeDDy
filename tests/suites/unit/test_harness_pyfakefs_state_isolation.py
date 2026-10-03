"""Regression: a leaked pyfakefs global flag must not crash a later ``fs`` test.

Reproduces the ubuntu-latest CI failure in which a leftover
``pyfakefs.fake_os.FakeOsModule.use_original = True`` (a process-global class
attribute) made a subsequent test's ``fs``-fixture SETUP raise
``AttributeError: module 'os' has no attribute 'dir'``.

The first test emulates the upstream leaker; the second requests the ``fs``
fixture. Both share an xdist group so the leak reaches the second test on the
same worker. The harness-level autouse reset fixture in ``tests/conftest.py``
clears the flag at every test boundary, so both tests pass once the fix is in
place; without it, the second test errors in SETUP.
"""

from pyfakefs import fake_os
import pytest

_GROUP = "pyfakefs_use_original_leak"


@pytest.mark.xdist_group(_GROUP)
def test_leaks_pyfakefs_use_original_flag():
    # Emulates the upstream test that leaves the global flag leaked True.
    fake_os.FakeOsModule.use_original = True
    assert fake_os.FakeOsModule.use_original is True


@pytest.mark.xdist_group(_GROUP)
def test_fs_fixture_still_works_after_leak(fs):
    # Reaching this body proves the `fs` fixture SETUP did not crash.
    fs.create_file("/app/example.txt", contents="ok")
    assert fake_os.FakeOsModule.use_original is False
    assert fs.exists("/app/example.txt")
