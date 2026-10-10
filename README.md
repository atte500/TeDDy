# TeDDy: the opinionated software engineering harness

> Because **you** should own the means of development

The [2025 DORA report](https://dora.dev/research/2025/) found that AI adoption does raise delivery throughput and product performance, but it stays negatively related to delivery stability: code moves faster but disproportionately more of it breaks. Any gains in raw speed are counterbalanced by increased effort needed for reviewing and reworking "slop" code to avoid technical defects and misalignment from compounding. Teams with fast feedback loops and loosely coupled systems see the most gain, while teams with inefficient processes and tight coupling see little or no benefit.

[Bain's 2026 Technology Report](https://www.bain.com/insights/the-missing-architecture-for-agentic-software-development-technology-report-2026/) reaches the same conclusion from the other side: the bottleneck has moved. The limiting factor is no longer the model, but the connective architecture around it. As they put it, "the system reverts to the throughput of its slowest human checkpoint." Better models will not by themselves fix the instability they cause.

TeDDy addresses these bottlenecks by bringing proven engineering practices like **Test-Driven Development, Hexagonal Architecture, and iterative delivery** directly into your agentic workflow, using only local plaintext files that you can read, review, and change, with nothing hidden in a proprietary database or the cloud.

**Don't want to read the rest? Watch me explain my thoughts behind TeDDy's design and a demo of it in action:**

[![Designing an Opinionated Harness for Coding Agents](https://img.youtube.com/vi/2j2fvRBGtag/0.jpg)](https://www.youtube.com/watch?v=2j2fvRBGtag)

## Why not just use...

### ...Skill.md files?

With skills, you most often carry out the process yourself, switching between multiple ad hoc skill files as you go, so you end up driving the process instead of setting the direction. Skills also add overhead, and they stack on top of your harness's own system prompt, which shifts under you with new versions and can conflict with your own instructions. A skill file describes a process; TeDDy runs it, splitting the work across specialist agents and keeping the instructions as part of the system prompt rather than the context window, where large skills get truncated and older ones get dropped as the session grows. Skills are best kept as a tactical addition, and your existing skill files still work inside TeDDy.

### ...Spec-driven development?

Spec-driven development makes you write down exactly what the software should do before writing any code. Leaving aside the fact that any spec detailed enough just becomes code, this is essentially just the [waterfall model](https://en.wikipedia.org/wiki/Waterfall_model) in a new outfit, which front-loads the analysis on the assumption that the requirements defined up front will be correct. But that assumption rarely holds. People often do not know what they want until they see it, and any non-trivial system will run into edge cases that could not have been predicted upfront.

Agile was born to shorten the loop between building something and using it, so that mistakes surface while they are still cheap to fix and the design can adapt to what you learn along the way. TeDDy does use specifications, but as living documents inside an iterative process built around incremental design.

### ...Automation?

A common reaction to the drawbacks agents cause, like more review and more rework, is to stack more agent automations on top, such as pre-PR review bots. This relocates the bottleneck instead of removing it. Bain's report puts it directly: companies that speed up code generation without redesigning the surrounding process "don't compound their gains; they redistribute their pain. Every bottleneck AI removes exposes the next one." Adding another review step on top of an unchanged process just moves the slowest checkpoint further down the line.

## What makes TeDDy special

1. **Markdown as the interface.**
Inspired by [Obsidian](https://obsidian.md/)'s file-over-app philosophy, the interface is your file system, not a chat box. The documents are the medium you and the agent communicate through, and you review and edit them in whichever editor you already use. Because the agent's response format is just plain Markdown, you are not confined to TeDDy's own CLI. You can paste an agent's system prompt and your project context into any chat interface, then either apply the returned actions yourself or run the plan through TeDDy to execute it.

2. **Local-first architecture.**
Inspired by the [UNIX philosophy](https://en.wikipedia.org/wiki/Unix_philosophy) of small, sharp tools communicating via plain text, everything TeDDy needs lives directly on disk in your workspace, with no cloud dependency and no vendor lock-in. Your configuration and the agent workflows are stored as plain, open files, keeping your setup transparent, searchable, and portable.

3. **Auditable by design.**
Inspired by [Git](https://git-scm.com/)'s model of a self-contained local ledger, every turn is stored in your local workspace in plaintext. Each turn records the agent's reasoning, justification, and expectations, so you can trace the agent's thinking even on models that never expose their thinking tokens. These files are designed to be easy to read, search, and audit programmatically.

## Why working code is not enough

A coding agent is a language model paired with a harness. LLMs are trained for next-token prediction and optimized for short, atomic tasks, so they are good at producing code that works in the moment and poorly suited to the long game of keeping code, intent, and a team aligned over time. Left alone, a model tries to generate the final solution in one shot, and the defects it introduces compound turn after turn.

Containing those defects has been the central problem of software engineering long before LLMs existed, and the practices that solved it for human teams work just as well for agents. The defects that reach production come in two kinds:

- **Technical:** code that does not work the way it was intended.
- **Misalignment:** code that works but is not what the user or the team actually wanted.

Most coding harnesses do little to address either one, which leaves users bolting on external systems like MCP servers, skill files, and spec-driven tooling. TeDDy addresses both:

- **Technical defects:** a strict **Test-Driven (Red-Green-Refactor)** cycle and **continuous delivery through Git**. The agent writes a test first and commits in small units, so errors surface early instead of stacking up. At startup the harness checks that Git and the pre-commit hooks are in place, so pre-commit checks (linters and quality gates) and post-commit test runs keep tests passing before and after every change, and a CI/CD workflow catches platform-dependent issues. The prompts and the response protocol make this the path of least resistance; the git hooks hold the line at the commit boundary.
- **Misalignment:** specific **Markdown documents** mediate every phase transition, anchoring the agents and giving you a high-level interface to steer the project. The workflow moves from **Specification Documents and Milestones** to **Component Design Docs** that enforce **Hexagonal Architecture** through defined ports and contracts, and features ship through **Vertical Slices** and **Gherkin Scenarios**, so you review and verify working pieces at the end of each iteration instead of watching the system drift from your vision.

<img src="./assets/matrix.png" alt="Workflow Matrix" />

## The TeDDy Workflow

TeDDy breaks down the development process into distinct agents, each with a specific mandate. Their interaction is mediated through documents, letting you steer the project at a high level throughout.

<img src="./assets/workflow-schematic.png" alt="TeDDy Workflow" />

1. **Pathfinder:** Navigates from a vague idea to a technically-grounded roadmap. Explores *why*, *what*, and *how*, then helps you concretize it into a plan.
2. **Architect:** Defines contracts, boundaries, and vertical slices for the Developer. Uses spikes to de-risk uncertain approaches before committing to an architecture.
3. **Prototyper:** Builds standalone prototypes to validate uncertain features before the Developer implements them.
4. **Developer:** Implements features one deliverable at a time using a strict **Red-Green-Refactor** loop.
5. **Debugger:** Uses the scientific method to isolate root causes by building minimal reproduction cases.
6. **Assistant:** A flexible agent that follows your instructions without enforcing a strict process. Use it as a template for custom agents or for tasks that don't require the full disciplined workflow.

> **Note:** Each agent's workflow is defined in plain-text XML files under `.teddy/prompts/`. You can customize any agent to fit your needs or create new ones for specific use cases.

## Getting Started

### Prerequisites
- Python 3.11 or later.
- `pip` (included with Python) or `uv` (recommended).

### Install TeDDy

```bash
uv tool install teddy-cli
```

### Initialize

```bash
teddy init
```

Use subcommands to overwrite specific files with defaults:

- `teddy init prompts`: Overwrite bundled prompt XMLs in `.teddy/prompts/` (useful after upgrades).
- `teddy init config`: Overwrite config.yaml, .gitignore, and init.context with defaults. Preserves an existing `.env` (create-only).
- `teddy init templates`: Overwrite bundled Markdown templates in `docs/templates/` with defaults (useful after upgrades).

### Configuration

Your first `teddy start` runs an interactive setup and saves your LLM API key (`.teddy/.env`) and editor (`.teddy/config.yaml`). To configure manually instead, edit `.teddy/config.yaml`:
- `llm.model`: a model path from [openrouter.ai/models](https://openrouter.ai/models) (default: OpenRouter).
- `llm.api_key`: defaults to `${TEDDY_LLM_API_KEY}`; put your key in `.teddy/.env` (a literal value here also works).
- `editor`: any command in `PATH` or an absolute path to an executable, or `"disabled"` to turn editing off.

All `llm.*` keys pass through to [LiteLLM](https://docs.litellm.ai/docs/completion/input), so any of its parameters (e.g. `extra_body`) work here.

### Start a session

```bash
teddy start
```

Run with `--yolo` / `-y` for automatic approval:

```bash
teddy start -y
```

To make automatic approval the default for every session, set `yolo_default: true` in `.teddy/config.yaml`. Pass `--no-yolo` / `-n` to force interactive mode for a single run.

Start a session with a specific agent and an initial instruction:

```bash
teddy start -a architect -m "Plan the auth module"
```

If you omit `-a`, the `pathfinder` agent is used by default. Pass just an initial message:

```bash
teddy start -m "Your instruction"
```

Resume the most recent session:

```bash
teddy resume
```

Resume a specific session by slug or path:

```bash
teddy resume my-feature-branch
teddy resume .teddy/sessions/20260825_151900-my-feature-branch
```

Interrupt a running session with `q` (or `Ctrl+C`) at any time: the action currently in flight is stopped immediately, the remaining actions are skipped, and the report is still written so you keep the full audit trail. You can then continue the session with:

```bash
teddy resume -m "your next instruction"
```

`resume -m` injects the message as your next turn which is especially handy if you want to jump in during an automated `--yolo` / `-y` run to steer the agent with additional instructions without having to wait for it to finish.

Resume an ongoing session with a different agent:

```bash
teddy resume -a developer
```

### Optional flags

- `--agent` / `-a`: Choose an agent persona (e.g., `pathfinder`, `architect`, `developer`). Default: `pathfinder`.
- `--context` / `-c`: Pass additional context files or directories. Repeatable (`-c a.py -c b.md`); comma-separated values are also accepted (`-c "a.py,b.md"`).
- `--model`: Override the default model.
- `--yolo` / `-y`: Auto-approve all actions (non-interactive). Set `yolo_default: true` in `.teddy/config.yaml` to make this the default for every session; `--no-yolo` / `-n` forces interactive mode for a single run.
- `--message` / `-m`: Provide an initial message or instruction. Use standalone with `start` or `resume`, or together with `--pipeline`.
- `--pipeline` / `-p`: Pipeline mode: auto-approves all actions, requires `--message` / `-m`, exits after the first `## Message`. Useful for CI and automated workflows.

### Browser chat usage

1. Copy the system prompt for your desired agent by running `teddy get-prompt` (e.g., `teddy get-prompt -a assistant`) to use in your preferred chat UI (eg. claude or google ai studio).
2. Run `teddy context` to copy your project context to the clipboard.
3. Paste it into an LLM chat interface alongside your request.
4. Have the model generate a Markdown plan.
5. Copy the plan and run `teddy execute` (or `teddy execute -y` for automatic execution).

### Installing Experimental Versions

To install or upgrade to the latest experimental (pre-release) version directly from PyPI:

```bash
uv tool install teddy-cli --pre --force
```

> **Note:** Experimental versions are published as PEP 440 dev pre-releases on PyPI and may include features that are not yet stable. Use with caution.

### Command Reference

| Command          | Description                                                                                                    |
| ---------------- | -------------------------------------------------------------------------------------------------------------- |
| `init`           | Initialize `.teddy` directory with defaults and pre-warm heavy imports. See subcommands below.                 |
| `init prompts`   | Overwrite bundled prompt XMLs in `.teddy/prompts/` with defaults.                                              |
| `init config`    | Overwrite config.yaml, .gitignore, and init.context with defaults. Preserves an existing `.env` (create-only). |
| `init templates` | Overwrite bundled Markdown templates in `docs/templates/` with defaults.                                       |
| `start`          | Start an interactive session.                                                                                  |
| `resume`         | Resume an existing session.                                                                                    |
| `update`         | Check for updates and display upgrade instructions.                                                            |
| `execute`        | Execute a Markdown plan. Reads from clipboard if no file path provided.                                        |
| `context`        | Gather project context (file tree + selected file contents) to clipboard.                                      |
| `get-prompt`     | Retrieve agent system prompts. Respects `.teddy/prompts/` overrides.                                           |

By default, `execute` and `context` copy their output to the clipboard. Use `--no-copy` to disable.

## Learn More

- [Project Roadmap & Vision](/docs/project/PROJECT.md)
- [System Architecture](/docs/architecture/ARCHITECTURE.md)
- [Agent Prompt Templates](/src/teddy_executor/resources/config/prompts/)
