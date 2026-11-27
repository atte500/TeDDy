# Milestone: SDLC Orchestrator
- **Status:** Planned
- **Depends On:** None
- **Specs:** [interactive-session-workflow](../specs/interactive-session-workflow.md)

## Motivation
Driving TeDDy's SDLC across multi-slice milestones currently requires manually tracking `Depends On` prerequisites, composing `teddy start` / `teddy resume` handoff commands, managing parallel git worktrees, and monitoring sessions across turns. That orchestration toil slows delivery even when engineers want to stay in the loop for design alignment and domain decisions.

This milestone introduces a deterministic, non-blocking SDLC orchestrator (`teddy orchestrate`) that automates dependency-aware dispatch, parallel worktree execution, and routine lifecycle transitions while preserving human-in-the-loop alignment gates, local-first session auditability, and branch-agnostic Git workflows.

## Requirements
1. **Committed-Tree Dependency Graph & Readiness Resolver:**
   - Support `teddy orchestrate` (all pending milestones and slices), `-m` (specific milestone targets), `-s` (specific slice targets), and `--dry-run` / JSON output to inspect the resolved dependency graph, blocked/ready items, and deterministic next persona without spawning agents.
   - Build the dependency DAG directly from `docs/project/milestones/*.md` and `docs/project/slices/*.md` without requiring `PROJECT.md`, strictly blocking items whose `Depends On` prerequisites are not `Completed`.
   - Read the committed tree of the starting `<base_branch>` (ignoring uncommitted working-tree drafts), rescanning after each integration and flagging in-flight slices in the Inbox if their committed definition changes mid-run.

2. **Worktree Workspace Lifecycle:**
   - Provision external git worktrees under `~/.teddy/wt/<repo-name>/<slice-slug>/` (configurable via `TEDDY_WORKTREE_DIR` or `.teddy/config.yaml`, disambiguating repo names only on collision) and create the slice branch with remote tracking (`git push -u origin <branch>`) when a remote is configured so existing project `push` tooling works unmodified.
   - Bridge gitignored `.teddy/` files (`config.yaml`, `.env`, `prompts/`, `init.context`, plus configurable project-specific copy paths) into worktrees and collect `.teddy/sessions/` back into the main repository before removing the worktree.

3. **Single-Item Runner & Deterministic Exit Classification:**
   - Route unblocked items deterministically from structured metadata (milestones missing slices to `architect`, `[ ] [Domain]` unknowns to the human Inbox, `[ ] [Technical|Functional|Harness]` unknowns to `prototyper`, clear slices to `developer`, plus optional ordered stage pipelines in `.teddy/config.yaml`).
   - Run `teddy start -p` / `teddy resume -p` for a single target while enforcing turn and cost guardrails, and classify exits deterministically from `plan.md` (`Status:`, `Plan Type:`, `Workflow:` checklist), `report.md`, and `slice.md` (`Completed`, `NEEDS_HUMAN`, or `RETRY`).

4. **Parallel Scheduling & Branch-Agnostic Integration:**
   - Run independent, non-overlapping unblocked slices concurrently in isolated worktrees (checking `## Impact` overlap), while allowing single-track sequential runs directly on `<base_branch>`.
   - Enforce global cumulative turn and session cost guardrails across all active tracks.
   - Serialize integration against `<base_branch>` without overwriting dirty working-tree files in the user's checkout, recovering from conflicts or post-integration test failures by merging `<base_branch>` into the worktree and running `teddy resume -p` on the original slice session.
   - Provide a `--no-tui` / non-TTY mode that emits clean prefixed status transitions and actionable `teddy resume` commands when human input is required.

5. **Non-Blocking Textual Dashboard & Inbox:**
   - Provide a Textual orchestrator dashboard in interactive terminals featuring a live `Tracks` pane (status, persona, turn, cost, log tail) and an `Inbox` queue for human escalations (`WAITING FOR INPUT`), supporting one-key approval (`y`), quick handoffs (`d` for Debugger, `a` for Architect), inline reply (`r`), `$EDITOR` composition/inspection (`e`/`v`), mid-run edit resolution, and notifications without pausing other running tracks.

## Constraints
- **100% Deterministic Control Plane:** No Decision Model, LLM router, or new Markdown response format inside the orchestrator; routing and exit classification rely strictly on structured Markdown fields, `config.yaml`, and deterministic state transitions.
- **No Tooling or Worker Prompt Coupling:** Do not modify `make push` / `tooling.md` or add branch/worktree-specific instructions to worker agent prompts.
- **Human Alignment Preserved:** `Pathfinder`, `Architect`, `Prototyper`, `Debugger`, and `BLOCKED 🔴` states always pause in the Inbox for explicit human action unless overridden via CLI flags or config.
- **Hexagonal & Safety Boundaries:** Maintain Constructor Injection and the `TeddyError` exception hierarchy; uncommitted working-tree edits must never trigger agent runs or be overwritten during integration.

## Slices
Pending architectural decomposition.
