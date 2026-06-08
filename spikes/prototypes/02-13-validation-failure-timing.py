#!/usr/bin/env python3
"""
Prototype: Validation Failure Pruning Timing (Slice 02-13)
Purpose: Validate moving Heuristic 4 inside the green-state guard.

Behavioral Assertions:
  1. Validation failure without non-VF report → preserved
  2. Validation failure with subsequent non-VF report → pruned
  3. Validation failure with current_status non-VF → pruned
  4. Chain of validation failures without non-VF report → all preserved
  5. Empty turn_statuses handled gracefully
  6. (Regression) Existing test with current_status=None should NOT prune anymore
  7. No validation failures → no-op

Usage:
    python spikes/prototypes/02-13-validation-failure-timing.py        # Non-interactive assertions
    python spikes/prototypes/02-13-validation-failure-timing.py --interactive  # Manual exploration
"""

import argparse
import re
import sys
from typing import Dict, Optional, Set, Any
from unittest.mock import create_autospec

# We need to import real domain objects
from teddy_executor.core.domain.models.project_context import ContextItem
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.services.session_pruning_service import (
    SessionPruningService,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


# ──────────────────────────────────────────────
# MODIFIED GUARD: non-VF report based
# ──────────────────────────────────────────────
def collect_turn_metadata_modified(
    self,
    items,
    prune_non_green: bool,
    prune_validation: bool,
    preserve_messages: bool = False,
) -> tuple[Dict[int, bool], set[int], set[int]]:
    """Modified _collect_turn_metadata that also collects non_vf_reports."""
    turn_statuses: Dict[int, bool] = {}
    validation_failures: set[int] = set()
    non_vf_reports: set[int] = set()  # NEW: turns with non-VF report on disk
    spared_turns: set[int] = set()
    checked_paths = set()

    for item in items:
        if item.scope != "Turn" or item.path in checked_paths:
            continue

        posix_path = item.path.replace("\\", "/")
        turn_id_str = self._extract_turn_id(posix_path)
        if not turn_id_str:
            continue

        turn_id = int(turn_id_str)
        checked_paths.add(item.path)

        # Heuristic 4: Validation failure detection
        if posix_path.endswith("report.md"):
            if prune_validation and self._check_report_failed_validation(item.path):
                validation_failures.add(turn_id)
            # NEW: Detect non-VF reports (report exists and is NOT a validation failure)
            if self._check_report_not_validation_failure(item.path):
                non_vf_reports.add(turn_id)

            # Sparing via user_request metadata
            if self._check_report_has_user_request(item.path):
                spared_turns.add(turn_id)

        # Heuristic 3: Non-green state (Check plan)
        if posix_path.endswith("plan.md"):
            is_failed = self._check_plan_failed(item.path)
            if prune_non_green:
                is_green = not is_failed
                turn_statuses[turn_id] = (
                    turn_statuses.get(turn_id, True) and is_green
                )

        # Sparing Rule: Successful Message Turns
        if preserve_messages and posix_path.endswith("plan.md"):
            if self._check_plan_is_message(item.path):
                report_path = item.path.replace("plan.md", "report.md")
                if self._check_report_is_success(report_path):
                    spared_turns.add(turn_id)

    # Store non_vf_reports for use in _apply_pruning_heuristics_modified
    self._non_vf_reports = non_vf_reports
    return turn_statuses, validation_failures, spared_turns


def apply_pruning_heuristics_modified(
    self,
    turn_statuses: Dict[int, bool],
    validation_failures: Set[int],
    prune_non_green: bool,
    current_status: Optional[str] = None,
) -> Dict[str, str]:
    """Modified version: Heuristic 4 guarded by non-VF report existence."""
    turns_to_prune: Dict[str, str] = {}

    # --- NEW GUARD: Non-VF report based ---
    non_vf_reports: set[int] = getattr(self, "_non_vf_reports", set())

    # Current turn is a non-VF anchor if its status is not "Validation Failed"
    is_currently_non_vf = (
        current_status is not None and "Validation Failed" not in current_status
    )

    # Find the latest non-VF report on disk
    latest_non_vf_turn = max(non_vf_reports) if non_vf_reports else -1

    # Heuristic 4: Validation Failure (guarded)
    for tid in sorted(validation_failures):
        # Prune if there is a non-VF report (on disk) after this VF turn
        # OR if current turn is non-VF (current turn is the latest, so it anchors all prior VFs)
        prune_vf = tid < latest_non_vf_turn
        if not prune_vf and is_currently_non_vf:
            # Current non-VF turn is the latest turn overall, so it anchors everything before it.
            # All on-disk VF turns must have occurred in earlier turns.
            prune_vf = True
        if prune_vf:
            turns_to_prune[str(tid)] = "Plan failed validation"

    # Heuristic 3: Recovery Cleanup (unchanged, uses green-state guard)
    is_currently_green = current_status is not None and "🟢" in current_status
    if prune_non_green and turn_statuses:
        latest_on_disk = max(turn_statuses.keys())
        is_latest_green = turn_statuses[latest_on_disk]
        if is_currently_green or is_latest_green:
            for tid, is_green in turn_statuses.items():
                if not is_green:
                    turns_to_prune.setdefault(
                        str(tid),
                        "Pruned failure history after successful recovery",
                    )

    return turns_to_prune


# Helper to check if a report exists and is NOT a validation failure
def _check_report_not_validation_failure(self, path: str) -> bool:
    """Checks if a report file exists and does NOT have validation failure status."""
    content = self._safe_read(path)
    if content:
        # Report exists; check if it is NOT a validation failure
        return not bool(
            re.search(
                r"^- \*\*Overall Status:\*\* Validation Failed",
                content,
                re.MULTILINE,
            )
        )
    return False  # File doesn't exist or unreadable, not a non-VF report


# ──────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────
def make_service() -> SessionPruningService:
    """Create a real SessionPruningService with mocked dependencies."""
    config = create_autospec(IConfigService, instance=True)
    config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.preserve_message_turns": True,
        "auto_pruning.max_turns_retention": 0,
        "auto_pruning.turn_context_threshold": 0,
    }.get(key, default)

    fs = create_autospec(IFileSystemManager, instance=True)

    # Default mock behavior: files exist and have default content
    fs.path_exists.return_value = True
    fs.read_file.return_value = ""

    service = SessionPruningService(config_service=config, file_system_manager=fs)

    # Monkey-patch the modified methods
    service._apply_pruning_heuristics = apply_pruning_heuristics_modified.__get__(
        service, SessionPruningService
    )
    service._collect_turn_metadata = collect_turn_metadata_modified.__get__(
        service, SessionPruningService
    )
    # Bind the new helper method
    service._check_report_not_validation_failure = (
        _check_report_not_validation_failure.__get__(service, SessionPruningService)
    )

    return service


def make_context(items: list[ContextItem]) -> ProjectContext:
    return ProjectContext(items=items, header="", content="")


def item(
    path: str,
    scope: str = "Turn",
    token_count: int = 100,
    git_status: str = " ",
    selected: bool = True,
) -> ContextItem:
    return ContextItem(
        path=path,
        scope=scope,
        token_count=token_count,
        git_status=git_status,
        selected=selected,
    )


def assert_selected(item: ContextItem, expected: bool) -> None:
    status = "✅" if item.selected == expected else "❌"
    reason = item.auto_prune_reason or "N/A"
    print(f"  {status} {item.path}: selected={item.selected} (expected={expected}, reason={reason})")
    assert item.selected == expected, (
        f"{item.path}: expected selected={expected}, got {item.selected}, reason={reason}"
    )


# ──────────────────────────────────────────────
# Scenario Tests
# ──────────────────────────────────────────────
def test_validation_failure_without_non_vf_report_preserved(service: SessionPruningService) -> None:
    """Heuristic 4: Validation failure without non-VF report → preserved."""
    print("\n[Test 1] Validation failure without non-VF report → preserved")

    # Setup: turn 01 has validation failure (report.md), no non-VF report on disk
    fs = service._file_system_manager
    fs.path_exists.return_value = True
    fs.read_file.return_value = "- **Overall Status:** Validation Failed"

    items = [
        item("01/report.md"),
    ]
    ctx = make_context(items)

    # current_status is "Validation Failed" → no non-VF anchor at all
    result = service.prune(ctx, current_status="Validation Failed")

    assert_selected(result.items[0], True)
    print("  ✅ PASSED: Validation failure preserved when no non-VF report exists")


def test_validation_failure_with_non_vf_report_pruned(service: SessionPruningService) -> None:
    """Heuristic 4: Validation failure with subsequent non-VF report → pruned."""
    print("\n[Test 2] Validation failure with non-VF report anchor → pruned")

    fs = service._file_system_manager

    # Turn 01: validation failure report
    # Turn 02: non-VF report (SUCCESS status) — this is the anchor
    def read_file_side_effect(path: str) -> str:
        if "01/report.md" in path:
            return "- **Overall Status:** Validation Failed"
        elif "02/report.md" in path:
            return "# Report\n- **Overall Status:** SUCCESS"
        return ""
    fs.read_file.side_effect = read_file_side_effect

    items = [
        item("01/report.md"),  # VF turn
        item("02/report.md"),  # Non-VF report → anchor
    ]
    ctx = make_context(items)

    # current_status is unused when there is an on-disk non-VF report
    result = service.prune(ctx, current_status="Validation Failed")

    # Turn 01 VF should be pruned because turn 02 has a non-VF report
    assert_selected(result.items[0], False)  # VF report pruned
    assert_selected(result.items[1], True)   # Non-VF report preserved
    print("  ✅ PASSED: Validation failure pruned when non-VF report anchor exists")


def test_validation_failure_with_current_status_non_vf_pruned(service: SessionPruningService) -> None:
    """Heuristic 4: Validation failure with current_status non-VF → pruned."""
    print("\n[Test 3] Validation failure with current_status non-VF → pruned")

    fs = service._file_system_manager
    fs.read_file.return_value = "- **Overall Status:** Validation Failed"
    fs.read_file.side_effect = None

    # Only one turn with validation failure, no other reports
    items = [
        item("01/report.md"),
    ]
    ctx = make_context(items)

    # current_status is SUCCESS (non-VF, no "Validation Failed") → acts as anchor after on-disk turn
    result = service.prune(ctx, current_status="SUCCESS")

    assert_selected(result.items[0], False)  # validation failure pruned because current turn is non-VF
    print("  ✅ PASSED: Validation failure pruned when current_status is non-VF")


def test_chain_validation_failures_all_preserved(service: SessionPruningService) -> None:
    """Heuristic 4: Chain of validation failures without non-VF report → all preserved."""
    print("\n[Test 4] Chain of validation failures without non-VF report → all preserved")

    fs = service._file_system_manager

    def read_file_side_effect(path: str) -> str:
        if "report.md" in path:
            return "- **Overall Status:** Validation Failed"
        return ""
    fs.read_file.side_effect = read_file_side_effect

    items = [
        item("01/report.md"),
        item("02/report.md"),
        item("03/report.md"),
    ]
    ctx = make_context(items)

    # current_status is "Validation Failed" → no non-VF anchor
    result = service.prune(ctx, current_status="Validation Failed")

    for i in range(3):
        assert_selected(result.items[i], True)
    print("  ✅ PASSED: All validation failures preserved in chain without non-VF report")


def test_empty_turn_statuses_handled(service: SessionPruningService) -> None:
    """Edge case: No report.md on disk, current_status is non-VF → no non-VF report on disk."""
    print("\n[Test 5] Empty turn_statuses handled gracefully")

    fs = service._file_system_manager

    # report.md exists with VF status, no other reports → no non-VF report on disk
    def read_file_side_effect(path: str) -> str:
        if "report.md" in path:
            return "- **Overall Status:** Validation Failed"
        return ""
    fs.read_file.side_effect = read_file_side_effect

    items = [
        item("01/report.md"),
    ]
    ctx = make_context(items)

    # current_status is also VF → no non-VF anchor at all
    result = service.prune(ctx, current_status="Validation Failed")

    # No non-VF report on disk and current turn is VF, so VF turn preserved
    assert_selected(result.items[0], True)
    print("  ✅ PASSED: Empty non-VF reports handled, validation failure preserved")


def test_regression_old_behavior_unchanged(service: SessionPruningService) -> None:
    """Regression: The existing test `test_prune_targets_anchored_validation_failure`
    passes current_status=None and expects the report to be preserved because:
    - The report has overall status SUCCESS (not a VF).
    - Our Heuristic 4 only looks at VF reports, so this report is ignored."""
    print("\n[Regression] Existing test: SUCCESS report with current_status=None → preserved")

    fs = service._file_system_manager

    # Existing test has a report with "Validation Failed" in note, but overall status is SUCCESS
    fs.read_file.return_value = (
        "# Report\n"
        "Note: We previously had a Validation Failed error.\n"
        "- **Overall Status:** SUCCESS"
    )
    fs.read_file.side_effect = None

    items = [
        item("01/report.md"),
    ]
    ctx = make_context(items)

    # This matches the existing test: current_status=None, no other reports
    result = service.prune(ctx, current_status=None)

    # This report is NOT a validation failure (status is SUCCESS), so it won't be pruned.
    # Neither Heuristic 3 nor Heuristic 4 applies.
    assert_selected(result.items[0], True)

    # Now test: if we have a VF report AND a later non-VF report, VF is pruned
    def read_file_side_effect(path: str) -> str:
        if "01/report.md" in path:
            return "- **Overall Status:** Validation Failed"
        elif "02/report.md" in path:
            return "# Report\n- **Overall Status:** SUCCESS"
        return ""
    fs.read_file.side_effect = read_file_side_effect

    items_vf = [
        item("01/report.md"),
        item("02/report.md"),  # Non-VF report → anchor
    ]
    ctx_vf = make_context(items_vf)

    result_vf = service.prune(ctx_vf, current_status="Validation Failed")

    assert_selected(result_vf.items[0], False)  # VF report pruned
    assert_selected(result_vf.items[1], True)   # Non-VF report preserved
    print("  ✅ PASSED: Regression validated — existing test behavior is unchanged; VF pruning now requires non-VF anchor")


def test_no_validation_failure_no_op(service: SessionPruningService) -> None:
    """Edge case: No validation failures → Heuristic 4 no-op."""
    print("\n[Test 6] No validation failures → Heuristic 4 no-op")

    fs = service._file_system_manager
    fs.read_file.return_value = "# Report\n- **Overall Status:** SUCCESS"
    fs.read_file.side_effect = None

    items = [
        item("01/report.md"),
        item("02/report.md"),
    ]
    ctx = make_context(items)

    result = service.prune(ctx, current_status="SUCCESS")

    assert_selected(result.items[0], True)
    assert_selected(result.items[1], True)
    print("  ✅ PASSED: No validation failures, no pruning applied")


def test_interactive_mode(service: SessionPruningService) -> None:
    """Interactive mode for manual exploration."""
    print("\n" + "=" * 60)
    print("Interactive Mode: Validation Failure Pruning Timing")
    print("=" * 60)
    print("This prototype demonstrates the modified Heuristic 4 behavior.")
    print()
    print("Scenarios:")
    print("  1 - Validation failure without non-VF report → preserved")
    print("  2 - Validation failure with subsequent non-VF report → pruned")
    print("  3 - Chain of validation failures → all preserved")
    print("  q - Quit")
    print()

    while True:
        choice = input("Select scenario (1-3, q): ").strip()
        if choice == "1":
            print("\n--- Scenario 1: No non-VF report anchor ---")
            fs = service._file_system_manager
            fs.read_file.return_value = "- **Overall Status:** Validation Failed"
            fs.read_file.side_effect = None
            ctx = make_context([item("01/report.md")])
            result = service.prune(ctx, current_status="Validation Failed")
            print(f"  Item 01/report.md: selected={result.items[0].selected}")
            print("  ✓ Validation failure preserved (no non-VF anchor)")
        elif choice == "2":
            print("\n--- Scenario 2: With non-VF report anchor ---")
            fs = service._file_system_manager
            def read_file_side_effect(path: str) -> str:
                if "01/report.md" in path:
                    return "- **Overall Status:** Validation Failed"
                elif "02/report.md" in path:
                    return "# Report\n- **Overall Status:** SUCCESS"
                return ""
            fs.read_file.side_effect = read_file_side_effect
            ctx = make_context([item("01/report.md"), item("02/report.md")])
            result = service.prune(ctx, current_status="Validation Failed")
            print(f"  Item 01/report.md: selected={result.items[0].selected}")
            print(f"  Item 02/report.md:   selected={result.items[1].selected}")
            print("  ✓ Validation failure pruned (non-VF report anchor exists)")
        elif choice == "3":
            print("\n--- Scenario 3: Chain of failures ---")
            fs = service._file_system_manager
            fs.read_file.return_value = "- **Overall Status:** Validation Failed"
            fs.read_file.side_effect = None
            ctx = make_context([item("01/report.md"), item("02/report.md"), item("03/report.md")])
            result = service.prune(ctx, current_status="Validation Failed")
            for i, it in enumerate(result.items):
                print(f"  Item {it.path}: selected={it.selected}")
            print("  ✓ All validation failures preserved (no non-VF anchor)")
        elif choice == "q":
            break
        else:
            print("  Invalid choice. Try again.")
        print()


def main():
    parser = argparse.ArgumentParser(description="Slice 02-13 validation failure pruning timing prototype")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive exploration mode")
    args = parser.parse_args()

    service = make_service()

    if args.interactive:
        test_interactive_mode(service)
    else:
        # Non-interactive mode: run all assertions
        print("=" * 60)
        print("Slice 02-13: Validation Failure Pruning Timing")
        print("Non-interactive assertion mode")
        print("=" * 60)

        test_validation_failure_without_non_vf_report_preserved(service)
        test_validation_failure_with_non_vf_report_pruned(service)
        test_validation_failure_with_current_status_non_vf_pruned(service)
        test_chain_validation_failures_all_preserved(service)
        test_empty_turn_statuses_handled(service)
        test_regression_old_behavior_unchanged(service)
        test_no_validation_failure_no_op(service)

        print("\n" + "=" * 60)
        print("All assertions passed! ✅")
        print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())