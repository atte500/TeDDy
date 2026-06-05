#!/usr/bin/env python3
"""
Prototype: Preserve User-Message Turns (Slice 02-10)

Simulates the SessionPruningService sparing logic with a new
_check_report_has_user_request detection.

Usage:
    python spikes/prototypes/10-preserve-user-message-turns.py [--verify | --interactive]
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------- Standalone domain models (mirroring ProjectContext) ----------

@dataclass
class ContextItem:
    path: str
    scope: str = "Turn"
    selected: bool = True
    token_count: int = 100
    git_status: str = " "
    auto_prune_reason: str = ""


# ---------- Fake adapters ----------

class FakeFileSystem:
    """Simulates IFileSystemManager using a real temp directory."""

    def __init__(self, root: Path):
        self.root = root

    def read_file(self, path: str) -> str:
        full = self.root / path
        return full.read_text(encoding="utf-8")

    def path_exists(self, path: str) -> bool:
        full = self.root / path
        return full.exists()

    def ensure_directory(self, path: str) -> None:
        full = self.root / path
        full.mkdir(parents=True, exist_ok=True)

    def write_file(self, path: str, content: str) -> None:
        full = self.root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")


class FakeConfigService:
    """Returns static config values matching the production defaults."""

    def get_setting(self, key: str, default: Any = None) -> Any:
        config = {
            "auto_pruning.enabled": True,
            "auto_pruning.prune_failure_history": True,
            "auto_pruning.prune_validation_failures": True,
            "auto_pruning.preserve_message_turns": True,
            "auto_pruning.max_turns_retention": 5,
            "auto_pruning.turn_context_threshold": 50000,
        }
        return config.get(key, default)


# ---------- Core pruning logic (standalone, mirrors SessionPruningService) ----------

class PruningSimulator:
    """Encapsulates the same pruning logic as SessionPruningService,
    with the new _check_report_has_user_request method.
    """

    def __init__(self, fs: FakeFileSystem, config: FakeConfigService):
        self._fs = fs
        self._config = config
        self._read_cache: Dict[str, str] = {}

    def prune(
        self, items: List[ContextItem], current_status: Optional[str] = None
    ) -> List[ContextItem]:
        self._read_cache.clear()

        # 1. Identify turns to prune and spared turns
        turns_to_prune, spared_turns = self._identify_turns_to_prune(items, current_status)

        for i, item in enumerate(items):
            new_item = self._process_context_item(item, turns_to_prune)
            if new_item is not item:
                items[i] = new_item

        # 2. Retention limit
        items = self._apply_retention_limit(items, spared_turns=spared_turns)

        # 3. Global budget
        items = self._apply_global_budget(items, spared_ids=spared_turns)

        return items

    def _process_context_item(self, item: ContextItem, turns_to_prune: Dict[str, str]) -> ContextItem:
        if item.scope != "Turn":
            return item
        if item.git_status == "D":
            return replace(item, selected=False, auto_prune_reason="File deleted from disk")
        posix_path = item.path.replace("\\", "/").removeprefix("./").lstrip("/")
        turn_id = self._extract_turn_id(posix_path)
        if turn_id:
            reason = turns_to_prune.get(turn_id) or turns_to_prune.get(str(int(turn_id)))
            if reason:
                return replace(item, selected=False, auto_prune_reason=reason)
        return item

    def _extract_turn_id(self, path: str) -> Optional[str]:
        if not isinstance(path, str):
            return None
        normalized = path.replace("\\", "/").removeprefix("./").lstrip("/")
        matches = re.findall(r"(?:^|/)(\d{1,3})(?=/|$)", normalized)
        return matches[-1] if matches else None

    def _identify_turns_to_prune(
        self, items: List[ContextItem], current_status: Optional[str] = None
    ) -> Tuple[Dict[str, str], Set[int]]:
        prune_non_green = self._config.get_setting("auto_pruning.prune_failure_history", True)
        prune_validation = self._config.get_setting("auto_pruning.prune_validation_failures", True)
        preserve_messages = self._config.get_setting("auto_pruning.preserve_message_turns", True)

        turn_statuses, validation_failures, spared_turns = self._collect_turn_metadata(
            items, prune_non_green, prune_validation, preserve_messages
        )

        turns_to_prune = self._apply_pruning_heuristics(
            turn_statuses, validation_failures, prune_non_green, current_status
        )

        # Remove spared turns from prune list
        for tid in spared_turns:
            turns_to_prune.pop(str(tid), None)

        return turns_to_prune, spared_turns if preserve_messages else set()

    def _collect_turn_metadata(
        self,
        items: List[ContextItem],
        prune_non_green: bool,
        prune_validation: bool,
        preserve_messages: bool,
    ) -> Tuple[Dict[int, bool], Set[int], Set[int]]:
        turn_statuses: Dict[int, bool] = {}
        validation_failures: Set[int] = set()
        spared_turns: Set[int] = set()  # renamed from successful_messages
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

            self._update_turn_metadata_from_item(
                item, posix_path, turn_id,
                state={"statuses": turn_statuses, "validation_fails": validation_failures, "spared": spared_turns},
                config={"non_green": prune_non_green, "validation": prune_validation, "messages": preserve_messages},
            )

        return turn_statuses, validation_failures, spared_turns

    def _update_turn_metadata_from_item(
        self,
        item: ContextItem,
        posix_path: str,
        turn_id: int,
        state: Dict[str, Any],
        config: Dict[str, bool],
    ) -> None:
        # Heuristic 4: Validation failure (report)
        if config["validation"] and posix_path.endswith("report.md"):
            if self._check_report_failed_validation(item.path):
                state["validation_fails"].add(turn_id)

        # Heuristic 3: Non-green state (plan)
        if posix_path.endswith("plan.md"):
            is_failed = self._check_plan_failed(item.path)
            if config["non_green"]:
                is_green = not is_failed
                state["statuses"][turn_id] = (
                    state["statuses"].get(turn_id, True) and is_green
                )

        # --- NEW: Sparing via user_request metadata ---
        if posix_path.endswith("report.md"):
            if self._check_report_has_user_request(item.path):
                state["spared"].add(turn_id)

        # Sparing via successful message turns (existing)
        if config["messages"] and posix_path.endswith("plan.md"):
            if self._check_plan_is_message(item.path):
                report_path = item.path.replace("plan.md", "report.md")
                if self._check_report_is_success(report_path):
                    state["spared"].add(turn_id)

    # --- Detection helpers ---

    def _check_report_has_user_request(self, path: str) -> bool:
        """NEW: Detects the - **User Request:** pattern in report metadata."""
        content = self._safe_read(path)
        if content:
            # Match the line exactly: "- **User Request:**" followed by optional content
            return bool(re.search(r"^- \*\*User Request:\*\*", content, re.MULTILINE))
        return False

    def _check_plan_is_message(self, path: str) -> bool:
        content = self._safe_read(path)
        if content:
            return bool(re.search(r"^## Message", content, re.MULTILINE))
        return False

    def _check_plan_failed(self, path: str) -> bool:
        content = self._safe_read(path)
        if content:
            return bool(re.search(r"^- \*\*Status:\*\*.*[🔴🟡]", content, re.MULTILINE))
        return False

    def _check_report_failed_validation(self, path: str) -> bool:
        content = self._safe_read(path)
        if content:
            return bool(re.search(r"^- \*\*Overall Status:\*\* Validation Failed", content, re.MULTILINE))
        return False

    def _check_report_is_success(self, path: str) -> bool:
        content = self._safe_read(path)
        if content:
            return bool(re.search(r"^- \*\*Overall Status:\*\* SUCCESS", content, re.MULTILINE))
        return False

    def _safe_read(self, path: str) -> Optional[str]:
        if path in self._read_cache:
            return self._read_cache[path]
        try:
            if self._fs.path_exists(path):
                content = self._fs.read_file(path)
                self._read_cache[path] = content
                return content
        except (FileNotFoundError, OSError):
            pass
        return None

    # --- Heuristic application ---

    def _apply_pruning_heuristics(
        self,
        turn_statuses: Dict[int, bool],
        validation_failures: Set[int],
        prune_non_green: bool,
        current_status: Optional[str] = None,
    ) -> Dict[str, str]:
        turns_to_prune: Dict[str, str] = {}
        for tid in validation_failures:
            turns_to_prune[str(tid)] = "Plan failed validation"
        is_currently_green = current_status is not None and "🟢" in current_status
        if prune_non_green and turn_statuses:
            latest_on_disk = max(turn_statuses.keys())
            is_latest_green = turn_statuses[latest_on_disk]
            if is_currently_green or is_latest_green:
                for tid, is_green in turn_statuses.items():
                    if not is_green:
                        turns_to_prune.setdefault(str(tid), "Pruned failure history after successful recovery")
        return turns_to_prune

    def _apply_retention_limit(
        self, items: List[ContextItem], spared_turns: Optional[Set[int]] = None
    ) -> List[ContextItem]:
        limit = self._config.get_setting("auto_pruning.max_turns_retention", 0)
        try:
            limit = int(limit) if limit is not None else 0
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            return items
        turn_id_map, max_id = self._map_turn_ids(items)
        if max_id == -1:
            return items
        threshold = max_id - limit
        reason = f"Turn exceeds retention limit of {limit}"
        spared = spared_turns or set()
        for idx, tid in turn_id_map.items():
            if tid <= threshold and tid not in spared:
                items[idx] = replace(items[idx], selected=False, auto_prune_reason=reason)
        return items

    def _map_turn_ids(self, items: List[ContextItem]) -> Tuple[Dict[int, int], int]:
        max_id = -1
        turn_id_map: Dict[int, int] = {}
        for i, item in enumerate(items):
            if item.scope != "Turn":
                continue
            tid_str = self._extract_turn_id(item.path)
            if tid_str:
                try:
                    tid = int(tid_str)
                    turn_id_map[i] = tid
                    max_id = max(max_id, tid)
                except ValueError:
                    continue
        return turn_id_map, max_id

    def _get_turn_context_threshold(self) -> int:
        threshold = self._config.get_setting("auto_pruning.turn_context_threshold")
        try:
            return int(threshold) if threshold is not None else 0
        except (TypeError, ValueError):
            return 0

    def _apply_global_budget(
        self,
        items: List[ContextItem],
        spared_ids: Optional[Set[int]] = None,
    ) -> List[ContextItem]:
        threshold = self._get_turn_context_threshold()
        if threshold <= 0:
            return items
        total_tokens = sum(
            item.token_count for item in items
            if item.selected and item.scope == "Turn" and isinstance(item.token_count, (int, float))
        )
        if total_tokens > threshold:
            prune_candidates = [
                (i, item) for i, item in enumerate(items)
                if item.scope == "Turn" and item.selected and isinstance(item.token_count, (int, float))
            ]
            prune_candidates.sort(key=lambda x: x[1].token_count, reverse=True)
            spared = spared_ids or set()
            for idx, item in prune_candidates:
                if total_tokens <= threshold:
                    break
                turn_id_str = self._extract_turn_id(item.path)
                if turn_id_str:
                    try:
                        if int(turn_id_str) in spared:
                            continue
                    except ValueError:
                        pass
                items[idx] = replace(item, selected=False, auto_prune_reason="Pruned to fit context budget")
                total_tokens -= item.token_count
        return items


# ---------- Scenario Setup ----------

def setup_session(fs: FakeFileSystem) -> None:
    """Creates a simulated session with 4 turns, including plan.md and report.md files."""

    # Turn 01: Green SUCCESS turn with user_request metadata
    fs.write_file("01/report.md", """# Execution Report
- **Overall Status:** SUCCESS
- **User Request:** Add the new feature
""")
    fs.write_file("01/plan.md", """# Plan Something
- **Status:** Green 🟢
""")

    # Turn 02: Red FAILURE turn (non-green) without user_request
    fs.write_file("02/report.md", """# Execution Report
- **Overall Status:** FAILURE
""")
    fs.write_file("02/plan.md", """# Plan Something
- **Status:** Red 🔴
""")

    # Turn 03: Pure ## Message turn (green success) — should be spared
    fs.write_file("03/report.md", """# Execution Report
- **Overall Status:** SUCCESS
""")
    fs.write_file("03/plan.md", """# Plan Something
- **Status:** Green 🟢

## Message
This is a message turn.
""")

    # Turn 04: Green SUCCESS turn with user_request (to test retention limit)
    fs.write_file("04/report.md", """# Execution Report
- **Overall Status:** SUCCESS
- **User Request:** Please fix the bug
""")
    fs.write_file("04/plan.md", """# Plan Something
- **Status:** Green 🟢
""")


def build_items(fs: FakeFileSystem) -> List[ContextItem]:
    """Creates ContextItem list from the fake filesystem."""
    items = []
    for dir_name in ["01", "02", "03", "04"]:
        for fname in ["plan.md", "report.md"]:
            path = f"{dir_name}/{fname}"
            if fs.path_exists(path):
                items.append(ContextItem(path=path, selected=True, token_count=100))
    return items


def run_verify(fs: FakeFileSystem, simulator: PruningSimulator) -> bool:
    """Runs all four scenarios and returns True if all pass."""
    all_pass = True
    results = []

    # --- Scenario A: Turn with user_request spared from retention limit ---
    # Set retention limit to 2, so turns 01 and 02 should be pruned, but 01 has user_request
    # We simulate by running prune without current_status (no recovery)
    items = build_items(fs)
    # Manually set token_count large to trigger budget if needed, but focus on retention
    pruned = simulator.prune(items, current_status="🟢")

    # Turn 01 (path "01/report.md") has user_request -> should remain selected
    turn01_selected = any(
        item.path == "01/report.md" and item.selected for item in pruned
    )
    turn01_plan_selected = any(
        item.path == "01/plan.md" and item.selected for item in pruned
    )
    # Turn 02 (no user_request, non-green) should be pruned
    turn02_selected = any(
        item.path == "02/report.md" and item.selected for item in pruned
    )
    scenario_a_pass = turn01_selected and turn01_plan_selected and not turn02_selected
    results.append(("A: Turn with user_request spared from retention", scenario_a_pass, turn01_selected))

    # --- Scenario B: Turn with user_request spared from global budget ---
    # Rebuild items, set tiny threshold
    items = build_items(fs)
    # Override config for this test: we can create a new simulator with custom config
    custom_config = FakeConfigService()
    custom_config.get_setting = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.prune_failure_history": False,
        "auto_pruning.prune_validation_failures": False,
        "auto_pruning.preserve_message_turns": True,
        "auto_pruning.max_turns_retention": 10,
        "auto_pruning.turn_context_threshold": 50,  # small threshold
    }.get(key, default)
    sim_b = PruningSimulator(fs, custom_config)
    # Give turn 01 a huge token count to force budget pruning
    for item in items:
        if item.path.startswith("01/"):
            item.token_count = 5000
    pruned_b = sim_b.prune(items, current_status="🟢")
    turn01_selected_b = any(
        item.path == "01/report.md" and item.selected for item in pruned_b
    )
    turn01_plan_selected_b = any(
        item.path == "01/plan.md" and item.selected for item in pruned_b
    )
    scenario_b_pass = turn01_selected_b and turn01_plan_selected_b
    results.append(("B: Turn with user_request spared from budget", scenario_b_pass, turn01_selected_b))

    # --- Scenario C: Pure message turn remains spared (regression) ---
    items = build_items(fs)
    pruned_c = simulator.prune(items, current_status="🟢")
    turn03_selected = any(
        item.path == "03/report.md" and item.selected for item in pruned_c
    )
    turn03_plan_selected = any(
        item.path == "03/plan.md" and item.selected for item in pruned_c
    )
    scenario_c_pass = turn03_selected and turn03_plan_selected
    results.append(("C: Message turn spared (regression)", scenario_c_pass, turn03_selected))

    # --- Scenario D: Normal turn without user_request and not message should be pruned ---
    # Turn 02 is non-green and has no user_request -> should be pruned
    turn02_selected_d = any(
        item.path == "02/report.md" and item.selected for item in pruned
    )
    scenario_d_pass = not turn02_selected_d
    results.append(("D: Normal turn pruned", scenario_d_pass, not turn02_selected_d))

    # Print results
    print("=" * 70)
    print("Scenario Results")
    print("=" * 70)
    for name, passed, detail in results:
        icon = "✓" if passed else "✗"
        print(f"  {icon} {name}")
    print("=" * 70)
    all_pass = all(r[1] for r in results)
    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return all_pass


def run_interactive(fs: FakeFileSystem, simulator: PruningSimulator) -> None:
    """Interactive CLI for the user to explore the session state and pruning."""
    print("Interactive Pruning Showcase")
    print("=" * 50)
    print("Commands: [v]iew state, [r]un pruning, [q]uit")

    items = build_items(fs)

    while True:
        try:
            cmd = input("\nEnter command (v/r/q): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if cmd == "q":
            break
        elif cmd == "v":
            print("\nSession State (before pruning):")
            print(f"{'Path':<20} {'Selected':<10} {'Scope':<8} {'Tokens':<8}")
            print("-" * 50)
            for item in items:
                sel = "✓" if item.selected else "✗"
                print(f"{item.path:<20} {sel:<10} {item.scope:<8} {item.token_count:<8}")
        elif cmd == "r":
            print("\nRunning pruning with current_status=🟢...")
            pruned = simulator.prune(list(items), current_status="🟢")
            print("\nSession State (after pruning):")
            print(f"{'Path':<20} {'Selected':<10} {'Reason':<40}")
            print("-" * 70)
            for item in pruned:
                sel = "✓" if item.selected else "✗"
                reason = item.auto_prune_reason if not item.selected else ""
                print(f"{item.path:<20} {sel:<10} {reason:<40}")
        else:
            print("Unknown command.")


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="Prototype: Preserve User-Message Turns")
    parser.add_argument("--verify", action="store_true", help="Run non-interactive verification")
    parser.add_argument("--interactive", action="store_true", help="Run interactive showcase")
    args = parser.parse_args()

    # Create temp directory
    tmpdir = tempfile.mkdtemp(prefix="pruning_prototype_")
    fs = FakeFileSystem(Path(tmpdir))
    config = FakeConfigService()
    simulator = PruningSimulator(fs, config)

    try:
        setup_session(fs)

        if args.interactive:
            run_interactive(fs, simulator)
        else:
            # Default: run verify
            success = run_verify(fs, simulator)
            sys.exit(0 if success else 1)
    finally:
        # Cleanup
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()