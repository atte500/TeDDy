"""Unit tests for the shared test-harness path normalizer.

``mocking.to_posix_path`` is the single source of the harness'
cross-platform path normalization. It backs ``POSIXPathMock``'s mock-call
argument normalization (``_normalize_args``), the ``find_call_by_path``
assertion helper, and every path-matching ``side_effect`` that must compare an
incoming (already normalized) argument against a resolved baseline. These
tests pin its behaviour and prove those consumers are single-sourced through
it, so the Windows-only slash mismatch fixed for Bug 66 cannot silently
reappear.
"""

import pytest

from tests.harness.setup.mocking import (
    POSIXPathMock,
    path_exists_marker_absent,
    path_exists_marker_present,
    to_posix_path,
)


class TestToPosixPath:
    def test_converts_backslashes_to_forward_slashes(self):
        assert to_posix_path(r"C:\Users\runneradmin\bin") == (
            "C:/Users/runneradmin/bin"
        )

    def test_preserves_native_posix_paths(self):
        assert to_posix_path("/usr/local/bin/nvim") == "/usr/local/bin/nvim"

    def test_handles_mixed_separators(self):
        assert to_posix_path(r"C:\Users\runneradmin/bin\myeditor") == (
            "C:/Users/runneradmin/bin/myeditor"
        )

    def test_is_idempotent(self):
        once = to_posix_path(r"C:\Users\runneradmin/bin/myeditor")
        assert to_posix_path(once) == once


class TestPathMatchingConsumers:
    def test_mock_normalizes_the_first_string_argument(self):
        mock = POSIXPathMock()
        mock.which(r"C:\Users\runneradmin/bin/myeditor")
        assert mock.which.call_args.args[0] == "C:/Users/runneradmin/bin/myeditor"

    def test_find_call_by_path_matches_a_normalized_argument(self):
        mock = POSIXPathMock()
        mock.which(r"C:\Users\runneradmin/bin/myeditor")
        call = mock.find_call_by_path("which", r"C:\Users\runneradmin/bin/myeditor")
        assert call.args[0] == "C:/Users/runneradmin/bin/myeditor"

    def test_find_call_by_path_raises_for_an_unknown_path(self):
        mock = POSIXPathMock()
        mock.which("/usr/bin/nvim")
        with pytest.raises(AssertionError):
            mock.find_call_by_path("which", "/usr/bin/other")

    def test_side_effect_via_to_posix_path_is_windows_safe(self):
        # Simulate the Windows scenario behind Bug 66: the resolved baseline
        # keeps a backslash in the home component, while POSIXPathMock
        # normalizes the incoming argument before the side_effect runs. A raw
        # `==` would fail; comparing through the shared helper matches.
        baseline = r"C:\Users\runneradmin/bin/myeditor"
        mock = POSIXPathMock()
        mock.which.side_effect = lambda name: (
            baseline if to_posix_path(name) == to_posix_path(baseline) else None
        )
        assert mock.which(r"C:\Users\runneradmin/bin/myeditor") == baseline


class TestPathExistsMarkerAbsent:
    """The pending-turn ``path_exists`` double reports the marker absent.

    A never-dispatched pending turn records no ``execution.started`` marker, so
    the resume gate must read it absent while every other turn path keeps the
    suite's own answer. The factory single-sources the marker filename from the
    port, so a rename cannot leave this double matching a stale literal.
    """

    def test_marker_reads_absent_while_other_paths_forward_present(self) -> None:
        path_exists = path_exists_marker_absent(default=True)

        assert path_exists(".teddy/sessions/feature/05/execution.started") is False
        assert path_exists(".teddy/sessions/feature/05/report.md") is True

    def test_marker_reads_absent_while_other_paths_forward_absent(self) -> None:
        path_exists = path_exists_marker_absent(default=False)

        assert path_exists(".teddy/sessions/feature/05/execution.started") is False
        assert path_exists(".teddy/sessions/feature/05/report.md") is False

    def test_marker_path_matches_through_posix_normalization(self) -> None:
        path_exists = path_exists_marker_absent(default=True)

        assert path_exists(r".teddy\sessions\feature\05\execution.started") is False

    def test_bare_marker_filename_reads_absent(self) -> None:
        path_exists = path_exists_marker_absent(default=True)

        assert path_exists("execution.started") is False


class TestPathExistsMarkerPresent:
    """The killed-turn ``path_exists`` double reports the marker present.

    A turn killed mid-execution records ``execution.started``, so the resume
    gate must read it present while every other turn path keeps the suite's own
    answer. The factory single-sources the marker filename from the port, so a
    rename cannot leave this double matching a stale literal.
    """

    def test_marker_reads_present_while_other_paths_forward_absent(self) -> None:
        path_exists = path_exists_marker_present(default=False)

        assert path_exists(".teddy/sessions/feature/05/execution.started") is True
        assert path_exists(".teddy/sessions/feature/05/meta.yaml") is False

    def test_marker_reads_present_while_other_paths_forward_present(self) -> None:
        path_exists = path_exists_marker_present(default=True)

        assert path_exists(".teddy/sessions/feature/05/execution.started") is True
        assert path_exists(".teddy/sessions/feature/05/meta.yaml") is True

    def test_marker_path_matches_through_posix_normalization(self) -> None:
        path_exists = path_exists_marker_present(default=False)

        assert path_exists(r".teddy\sessions\feature\05\execution.started") is True

    def test_bare_marker_filename_reads_present(self) -> None:
        path_exists = path_exists_marker_present(default=False)

        assert path_exists("execution.started") is True
