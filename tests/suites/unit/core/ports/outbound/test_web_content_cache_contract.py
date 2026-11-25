from typing import Mapping, Optional

from teddy_executor.core.ports.outbound import IWebContentCache


class _ConformingCache:
    def load_entries(self, session_root: Optional[str]) -> dict[str, str]:
        return {}

    def merge_entries(
        self, session_root: Optional[str], entries: Mapping[str, str]
    ) -> None:
        return None


class _MissingMergeEntries:
    def load_entries(self, session_root: Optional[str]) -> dict[str, str]:
        return {}


def test_object_with_both_members_satisfies_the_port():
    assert isinstance(_ConformingCache(), IWebContentCache)


def test_object_without_merge_entries_does_not_satisfy_the_port():
    assert not isinstance(_MissingMergeEntries(), IWebContentCache)


def test_port_declares_load_entries():
    assert callable(getattr(IWebContentCache, "load_entries", None)), (
        "IWebContentCache must declare load_entries"
    )


def test_port_declares_merge_entries():
    assert callable(getattr(IWebContentCache, "merge_entries", None)), (
        "IWebContentCache must declare merge_entries"
    )
