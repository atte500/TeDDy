"""Fake GitHub CLI shim for the push-attribution probe.

Answers the exact query surface `make push` uses, reading its state from the
JSON file at $FAKE_GH_STATE:

    { "<sha>": { "workflows": { "<wf>": {"run_id": "<id>", "failures": [<job>...]} } } }

- `gh run list --commit <sha> --json workflowName --jq '.[].workflowName'`
      -> one workflow name per line for that SHA (sorted).
- `gh run list --commit <sha> --workflow <wf> --json databaseId --jq '.[0].databaseId'`
      -> the run id, or nothing when there is no run.
- `gh run view <id> --json jobs --jq '[...join(",")]'`
      -> the comma-joined failing job names (empty line when all passed).
- `gh run watch <id> --exit-status`
      -> exit 0 (the recipe tolerates failure with `|| true`).
"""

import json
import os
import sys


def _lag_active(sha):
    """Models CI registration lag for the pushed SHA.

    When $FAKE_GH_LAG_SHA equals `sha`, the FIRST $FAKE_GH_LAG_POLLS discovery
    calls report "no runs yet" (empty); subsequent calls report the real
    workflow list. The poll count persists in $FAKE_GH_LAG_FILE so it survives
    across the separate `gh` process invocations the recipe performs. An
    astronomical poll count models a run that NEVER registers. When
    $FAKE_GH_LAG_SHA is unset the shim is lag-free (backward compatible with
    the base-capture probe).
    """
    lag_sha = os.environ.get("FAKE_GH_LAG_SHA")
    if not lag_sha or sha != lag_sha:
        return False
    counter_path = os.environ.get("FAKE_GH_LAG_FILE")
    if not counter_path:
        return True
    polls = int(os.environ.get("FAKE_GH_LAG_POLLS", "0"))
    count = 0
    if os.path.exists(counter_path):
        with open(counter_path, encoding="utf-8") as handle:
            count = int(handle.read().strip() or "0")
    count += 1
    with open(counter_path, "w", encoding="utf-8") as handle:
        handle.write(str(count))
    return count <= polls


def _load_state():
    path = os.environ.get("FAKE_GH_STATE")
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv):
    data = _load_state()
    if data is None:
        return 1
    args = argv[1:]

    if args[:2] == ["run", "list"]:
        sha = None
        workflow = None
        index = 2
        while index < len(args):
            if args[index] == "--commit" and index + 1 < len(args):
                sha = args[index + 1]
                index += 2
            elif args[index] == "--workflow" and index + 1 < len(args):
                workflow = args[index + 1]
                index += 2
            else:
                index += 1
        runs = data.get(sha, {}).get("workflows", {})
        if workflow is None:
            if _lag_active(sha):
                return 0
            for name in sorted(runs):
                print(name)
        elif workflow in runs:
            print(runs[workflow]["run_id"])
        return 0

    if args[:2] == ["run", "view"]:
        run_id = args[2] if len(args) > 2 else None
        for sha_entry in data.values():
            for entry in sha_entry.get("workflows", {}).values():
                if entry["run_id"] == run_id:
                    print(",".join(entry["failures"]))
                    return 0
        return 1

    if args[:2] == ["run", "watch"]:
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))