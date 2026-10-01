#!/usr/bin/env bash
# =============================================================================
# Remote Debug Probe - Case File 53
# Persistent CI failure: Windows-only CRLF byte-exact turn-100 migration test.
#
# Legs:
#   LEG 0  - pathlib mechanism: default write_text translates \n -> os.linesep;
#            newline="" writes are verbatim (the shadow-fix mechanism).
#   LEG 0b - adapter mechanism: real LocalFileSystemAdapter.write_file vs
#            ShadowLocalFileSystemAdapter.write_file (newline="") bytes on disk.
#   LEG A  - reproduction: the exact CI-failing test with real adapter wiring
#            (expected FAIL on windows-latest, PASS on POSIX).
#   LEG B  - fix verification: identical scenario with SessionService wired to
#            the shadow adapter (expected PASS on every OS).
#
# Output is echoed and mirrored to spikes/debug/probe_output.txt (uploaded as
# the probe-result-windows artifact by .github/workflows/debug.yml).
# =============================================================================

set -u
set -o pipefail
cd "$(dirname "$0")/../.."

OUT="spikes/debug/probe_output.txt"

{
  echo "=== Remote Probe: Case 53 (Windows CRLF byte-exact migration) ==="
  echo "UTC: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  uv run python -c "import platform, sys; print('Python:', sys.version.split()[0]); print('Platform:', platform.platform())"

  echo ""
  echo "--- LEG 0: pathlib newline mechanism ---"
  uv run python - <<'PY0'
import os
import shutil
import tempfile
from pathlib import Path

d = Path(tempfile.mkdtemp(prefix="probe53_leg0_"))
try:
    default_path = d / "default.txt"
    verbatim_path = d / "verbatim.txt"
    default_path.write_text("line\n", encoding="utf-8")
    verbatim_path.write_text("line\n", encoding="utf-8", newline="")
    print("default write_text    ->", default_path.read_bytes())
    print("newline='' write_text ->", verbatim_path.read_bytes())
    print("os.linesep            ->", repr(os.linesep))
finally:
    shutil.rmtree(d, ignore_errors=True)
PY0

  echo ""
  echo "--- LEG 0b: adapter write_file mechanism (real vs shadow) ---"
  uv run python - <<'PY0B'
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "spikes/debug")

from shadow_local_file_system_adapter import ShadowLocalFileSystemAdapter
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.edit_simulator import EditSimulator

d = Path(tempfile.mkdtemp(prefix="probe53_leg0b_"))
try:
    try:
        sim = EditSimulator()
    except TypeError as e:
        print(f"[probe] EditSimulator() ctor mismatch ({e}); using None placeholder")
        print("[probe] safe: write_file never invokes the edit simulator")
        sim = None
    real = LocalFileSystemAdapter(edit_simulator=sim, root_dir=str(d))
    shadow = ShadowLocalFileSystemAdapter(edit_simulator=sim, root_dir=str(d))
    real.write_file("real.txt", "line\n")
    shadow.write_file("shadow.txt", "line\n")
    print("real   LocalFileSystemAdapter.write_file       ->", (d / "real.txt").read_bytes())
    print("shadow ShadowLocalFileSystemAdapter.write_file ->", (d / "shadow.txt").read_bytes())
    print("os.linesep                                     ->", repr(os.linesep))
finally:
    shutil.rmtree(d, ignore_errors=True)
PY0B

  echo ""
  echo "--- LEG A: reproduce - exact CI-failing test (real adapter wiring) ---"
  echo "Expectation: FAIL on windows-latest (CRLF assertion), PASS on POSIX."
  uv run pytest "tests/suites/integration/core/services/test_session_service.py::test_turn_100_migration_claims_unoccupied_root_and_preserves_sibling" -q --no-header 2>&1 | tail -n 40
  LEG_A=$?
  if [ "$LEG_A" -eq 0 ]; then
    echo "LEG A RESULT: PASS"
  else
    echo "LEG A RESULT: FAIL (expected on windows-latest)"
  fi

  echo ""
  echo "--- LEG B: verify fix - same scenario via shadow adapter (newline='') ---"
  echo "Expectation: PASS on every OS."
  mkdir -p tests/.tmp/probe53
  cat > tests/.tmp/probe53/test_turn_100_shadow_migration.py <<'PYTEST'
"""Probe (Case 53): turn-100 migration byte-exactness via the shadow adapter.

Replicates the CI-failing test
tests/suites/integration/core/services/test_session_service.py::
test_turn_100_migration_claims_unoccupied_root_and_preserves_sibling
with exactly ONE difference: SessionService's IFileSystemManager port is
wired with ShadowLocalFileSystemAdapter (write_file -> newline="") instead
of the real LocalFileSystemAdapter. Expected outcome: PASS on every OS,
including windows-latest.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

_SHADOW_DIR = Path(__file__).resolve().parents[3] / "spikes" / "debug"
sys.path.insert(0, str(_SHADOW_DIR))

from shadow_local_file_system_adapter import ShadowLocalFileSystemAdapter
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.services.session_service import SessionService


def _ledger_snapshot(session_dir: Path) -> dict[str, bytes]:
    """Mirrors the integration-suite helper (kept self-contained by design)."""
    return {
        "session.context": (session_dir / "session.context").read_bytes(),
        "developer.xml": (session_dir / "developer.xml").read_bytes(),
        "01/meta.yaml": (session_dir / "01" / "meta.yaml").read_bytes(),
    }


def test_turn_100_migration_with_shadow_adapter_is_byte_exact(
    tmp_path, monkeypatch, env
):
    """Identical Arrange/Act/Assert to the CI-failing test; shadow fs port."""
    # Arrange - identical to the CI-failing test.
    env.workspace = tmp_path
    env.with_real_filesystem()
    monkeypatch.chdir(tmp_path)

    # Build the migrating session with turn 99 completed (full ledger).
    session_dir = tmp_path / ".teddy" / "sessions" / "20260417_120000-foo"
    turn_99 = session_dir / "99"
    turn_99.mkdir(parents=True)
    (turn_99 / "report.md").write_text("# Report\n", encoding="utf-8")
    (turn_99 / "meta.yaml").write_text(
        "turn_id: '99'\nagent_name: 'developer'\n", encoding="utf-8"
    )
    (turn_99 / "plan.md").write_text("# Plan: Previous\n", encoding="utf-8")
    (turn_99 / "turn.context").write_text("", encoding="utf-8")
    (session_dir / "session.context").write_text("README.md\n", encoding="utf-8")
    (session_dir / "developer.xml").write_text(
        "<prompt>developer</prompt>", encoding="utf-8"
    )

    # Pre-create the live sibling session with its full ledger (occupied root).
    sibling = tmp_path / ".teddy" / "sessions" / "20260417_120000-foo-2"
    (sibling / "01").mkdir(parents=True)
    (sibling / "session.context").write_text("sibling-context\n", encoding="utf-8")
    (sibling / "developer.xml").write_text("<prompt>sibling</prompt>", encoding="utf-8")
    (sibling / "01" / "meta.yaml").write_text(
        "turn_id: '01'\nagent_name: 'developer'\n", encoding="utf-8"
    )
    before = _ledger_snapshot(sibling)

    # Act - identical flow, but the filesystem port is the shadow adapter.
    time_mock = env.mock_port(ITimeService)
    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    time_mock.now.return_value = fixed_now
    time_mock.now_utc.return_value = fixed_now.replace(tzinfo=timezone.utc)

    container = env.container
    shadow_fs = ShadowLocalFileSystemAdapter(
        edit_simulator=container.resolve(IEditSimulator),
        root_dir=str(tmp_path),
    )
    service = SessionService(
        file_system_manager=shadow_fs,
        repository=container.resolve(ISessionRepository),
        time_service=time_mock,
        prompt_manager=container.resolve(IPromptManager),
        init_service=container.resolve(IInitUseCase),
        config_service=container.resolve(IConfigService),
    )
    result = service.transition_to_next_turn((turn_99 / "plan.md").as_posix())

    # Assert - identical byte-exactness contract.
    assert result == ".teddy/sessions/20260417_120000-foo-3/01"
    claimed = tmp_path / ".teddy" / "sessions" / "20260417_120000-foo-3"
    assert (claimed / "01" / "meta.yaml").is_file()
    assert (claimed / "session.context").read_bytes() == b"README.md\n"
    assert (claimed / "developer.xml").read_bytes() == b"<prompt>developer</prompt>"
    after = _ledger_snapshot(sibling)
    assert after == before
PYTEST
  uv run pytest "tests/.tmp/probe53/test_turn_100_shadow_migration.py::test_turn_100_migration_with_shadow_adapter_is_byte_exact" -q --no-header 2>&1 | tail -n 40
  LEG_B=$?
  if [ "$LEG_B" -eq 0 ]; then
    echo "LEG B RESULT: PASS"
  else
    echo "LEG B RESULT: FAIL"
  fi

  echo ""
  echo "=== Probe complete: LEG_A exit=$LEG_A LEG_B exit=$LEG_B (0 = PASS) ==="
  exit "$LEG_B"
} | tee "$OUT"