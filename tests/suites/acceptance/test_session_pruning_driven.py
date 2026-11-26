"""Driven-session acceptance coverage for the retention rules.

The ceiling and its batch cadence are pinned in isolation at the service
boundary, but nothing proved what a *real* session carries from turn to turn.
These tests drive an actual session end to end with one canned LLM plan per
turn and read the manifested ``turn.context`` and the written ``input.md``
payload of every turn.

The drive is a single bounded ``start`` invocation: ``--max-turns`` binds the
production loop guard, and stdin supplies the per-turn instruction that the
planner's prompt tier reads. Supplying stdin instead of injecting ``resume -m``
matters: an injected message is written back onto the predecessor's report as
``## User Request``, which preserves that turn into the prune-exempt session
scope and would make the retention ceiling unreachable.

Pruning runs after ``input.md`` is written, so a drop never shows in the payload
of the turn that computed it: it shows in the manifest the next turn inherits
and, one turn later, in that turn's payload. Both halves are asserted here, the
payload side through the rendered ``### Turn N: Plan`` history headings.
"""

import re
from pathlib import Path

import pytest

from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment
from tests.suites.acceptance.helpers import mock_response, setup_project

_SESSION_NAME = "driven-pruning"
_INSTRUCTION = "Drive the pruning session"
_RECORD_PATH = re.compile(r"/(\d{1,3})/(?:plan|report)\.md$")


def _seed_config(root: Path, *, limit: int, batch: int) -> None:
    """Write the real config the drive reads: offline, keyed, retention-tuned."""
    (root / ".teddy").mkdir(exist_ok=True)
    (root / ".teddy" / "config.yaml").write_text(
        "llm:\n"
        "  api_key: driven-pruning-key\n"
        "workspace:\n"
        "  pull: false\n"
        "auto_pruning:\n"
        "  enabled: true\n"
        "  turn_context_threshold: 0\n"
        f"  max_turns_retention: {limit}\n"
        f"  retention_batch: {batch}\n",
        encoding="utf-8",
    )


def _register_production_guard(env: TestEnvironment) -> None:
    """Swap the harness guard mock for the production guard.

    ``TestEnvironment`` registers ``ISessionLoopGuard`` as an instance mock that
    never stops, so a bounded drive must install the production guard that
    honours the threaded ``--max-turns`` limit.
    """
    import punq

    from teddy_executor.core.ports.outbound.session_loop_guard import (
        ISessionLoopGuard,
    )
    from teddy_executor.core.services.session_loop_guard import (
        ProductionSessionLoopGuard,
    )

    env.container.register(
        ISessionLoopGuard, ProductionSessionLoopGuard, scope=punq.Scope.transient
    )


def _drive_session(
    root: Path, monkeypatch, *, limit: int, batch: int, turns: int
) -> Path:
    """Drive ``turns`` real turns with one canned plan each; return the session root."""
    env = (
        TestEnvironment(monkeypatch, root)
        .setup()
        .with_real_config()
        .with_real_shell()
        .with_real_interactor()
    )
    setup_project(root)
    _seed_config(root, limit=limit, batch=batch)
    _register_production_guard(env)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    llm.get_completion.side_effect = [
        mock_response(
            MarkdownPlanBuilder(f"Driven turn {turn}")
            .add_execute(f"echo driven-turn-{turn}")
            .build()
        )
        for turn in range(1, turns + 2)
    ]

    adapter = CliTestAdapter(monkeypatch, root)
    continuation = "".join(f"continue step {n}\n" for n in range(1, turns + 2))
    result = adapter.run_start(
        ["-y", "--max-turns", str(turns), "-m", _INSTRUCTION, _SESSION_NAME],
        input=continuation,
    )
    assert result.exit_code == 0, result.stdout

    sessions = sorted((root / ".teddy" / "sessions").glob(f"*{_SESSION_NAME}"))
    assert len(sessions) == 1, f"expected one session root, found {sessions}"
    return sessions[0]


def _manifest_turn_ids(session_root: Path, turn: int) -> set[int]:
    """The turn ids whose records the given turn carries forward."""
    manifest = session_root / f"{turn:02d}" / "turn.context"
    if not manifest.exists():
        return set()
    found: set[int] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = _RECORD_PATH.search(line.strip())
        if match:
            found.add(int(match.group(1)))
    return found


def _history_headings(turn_id: int) -> list[str]:
    """The rendered payload headings a turn's plan and report contribute."""
    return [f"### Turn {turn_id}: Plan", f"### Turn {turn_id}: Report"]


def _retained(ids: set[int], *, limit: int, batch: int) -> set[int]:
    """The ids the retention rule keeps once the ceiling is exceeded."""
    if len(ids) <= limit:
        return set(ids)
    depth = max(1, limit - batch + 1)
    return set(sorted(ids)[-depth:])


def _assert_drive_reached(session_root: Path, turns: int) -> None:
    """Fail with a drive-length message rather than a confusing manifest diff."""
    report = session_root / f"{turns:02d}" / "report.md"
    assert report.exists(), (
        f"the drive was expected to execute {turns} turns, but {report} is missing"
    )


def _assert_crossings(
    session_root: Path, *, limit: int, batch: int, turns: int
) -> list[set[int]]:
    """Assert every turn's inherited manifest matches the retention rule.

    For each driven turn the manifest it received is compared against the
    manifest the next turn inherits: the retained ids must follow
    ``max(1, limit - batch + 1)`` and the dropped ids must be gone from that next
    manifest. Each dropped turn must still be rendered in the crossing turn's
    own ``input.md`` — written before pruning — and must be absent from the
    following turn's payload, which was written after pruning.
    """
    crossings: list[set[int]] = []
    for turn in range(2, turns + 1):
        gathered = _manifest_turn_ids(session_root, turn)
        kept = _retained(gathered, limit=limit, batch=batch)
        dropped = gathered - kept

        inherited = _manifest_turn_ids(session_root, turn + 1)
        assert inherited == kept | {turn}, (
            f"turn {turn:02d} should hand turn {turn + 1:02d} "
            f"{sorted(kept | {turn})} but handed {sorted(inherited)}"
        )

        payload = (session_root / f"{turn:02d}" / "input.md").read_text(
            encoding="utf-8"
        )
        following_path = session_root / f"{turn + 1:02d}" / "input.md"
        following = (
            following_path.read_text(encoding="utf-8")
            if following_path.exists()
            else None
        )

        for turn_id in dropped:
            for heading in _history_headings(turn_id):
                assert heading in payload, (
                    f"turn {turn:02d} was rendered before pruning and must still "
                    f"carry {heading!r}"
                )
                if following is not None:
                    assert heading not in following, (
                        f"turn {turn + 1:02d} was rendered after pruning and must "
                        f"no longer carry {heading!r}"
                    )

        if dropped:
            crossings.append(dropped)
    return crossings


@pytest.mark.timeout(120)
def test_a_history_at_the_ceiling_is_never_pruned(tmp_path, monkeypatch):
    """Scenario: a session that only reaches the ceiling keeps every turn.

    Given ``max_turns_retention: 6`` and ``retention_batch: 2``
    When a real session is driven for seven turns with one canned plan each
    Then no turn is dropped from any inherited manifest
    And the last turn still carries every earlier turn's records
    """
    session_root = _drive_session(tmp_path, monkeypatch, limit=6, batch=2, turns=7)
    _assert_drive_reached(session_root, 7)

    crossings = _assert_crossings(session_root, limit=6, batch=2, turns=7)

    assert crossings == [], f"a history at the ceiling dropped {crossings}"
    assert _manifest_turn_ids(session_root, 7) == set(range(1, 7)), (
        "the last turn must still carry turns 1-6"
    )


@pytest.mark.timeout(120)
def test_each_batch_drops_the_oldest_turns_together(tmp_path, monkeypatch):
    """Scenario: every turn past the ceiling drops the oldest batch.

    Given ``max_turns_retention: 3`` and ``retention_batch: 2``
    When a real session is driven for eight turns with one canned plan each
    Then the first crossing drops turns 1 and 2 together
    And the second crossing drops turns 3 and 4 together
    And each crossing turn's payload still renders both dropped turns
    And the following turn's payload renders neither
    """
    session_root = _drive_session(tmp_path, monkeypatch, limit=3, batch=2, turns=8)
    _assert_drive_reached(session_root, 8)

    crossings = _assert_crossings(session_root, limit=3, batch=2, turns=8)

    assert [sorted(dropped) for dropped in crossings] == [[1, 2], [3, 4]], (
        f"expected two batches of the two oldest turns, got {crossings}"
    )


@pytest.mark.timeout(120)
def test_a_batch_of_one_drops_one_turn_per_crossing(tmp_path, monkeypatch):
    """Scenario: a batch of one keeps dropping one turn at a time.

    Given ``max_turns_retention: 3`` and ``retention_batch: 1``
    When a real session is driven for seven turns with one canned plan each
    Then three consecutive crossings each drop exactly the oldest turn
    """
    session_root = _drive_session(tmp_path, monkeypatch, limit=3, batch=1, turns=7)
    _assert_drive_reached(session_root, 7)

    crossings = _assert_crossings(session_root, limit=3, batch=1, turns=7)

    assert [sorted(dropped) for dropped in crossings] == [[1], [2], [3]], (
        f"expected one oldest turn dropped per crossing, got {crossings}"
    )
