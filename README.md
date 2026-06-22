# TeDDy: A Coding Harness Designed for Quality

<!-- Old video placeholder – will be updated with new release video
[![My Plan to Fix AI Coding](https://img.youtube.com/vi/By6wGuT-4sA/0.jpg)](https://www.youtube.com/watch?v=By6wGuT-4sA)
-->

AI code generation has become synonymous with high volume, low quality output. I believe it doesn't have to be that way.

TeDDy is an open-source coding harness that embeds proven software engineering practices like Test-Driven Development, Hexagonal Architecture, and iterative delivery.

## The Problem: Why LMMs Suck at Software Development

At its core, an AI agent is a language model paired with a harness. LLMs are trained for next-token prediction and optimized for short-term, atomic tasks. They naturally try to generate the final solution in one shot, which makes the defects they introduce compound the more you use them.

Addessing and preventing defects has been a central problem for software engineering long before LLMs became a thing. So maybe we should take a page out of real software engineering practices, that have been proven over decades and apply them to the AI-assisted software development as well.

We can conceptually split defects into two categories:

- **Technical Defects**: code that simply doesn't work the way it's intended.
- **Misalignment**: code that technically works but isn't what the user(s) actually wanted.

Current coding harnesses don't address these issues at all and frontier models are also hitting diminishing returns, leaving users trying to fix this by bolting on external systems like MCPs, skill files, spec-driven workflows, leading to a messy and frustrating development experience.

TeDDy instead attempts to solve these issues directly adopting, amongst others, the following strategies:
- **For Technical Defects:** TeDDy enforces a strict **Test-Driven (Red-Green-Refactor)** cycle. The AI must write a test first and verify it fails before writing any actual code. This catches errors early, before they compound.
- **For Misalignment:** Instead of specing everything upfront and building layer by layer, TeDDy builds features as **end-to-end vertical slices**. Each slice gives you a working piece of software to review and verify alignment.

**Additionally:** The use of Pre-commit quality checks and post-commit test suite run is designed to prevent defective code to reach your repo and allow different agents to work in parallel while ensuring continuous integration.

## Guiding Principles

### 1. Markdown as Interface

You interact with the AI through simple Markdown files you can edit, search, and manage with the tools you already use. No chat UI — your AI workflow lives alongside your code.

### 2. Human-Centric

Plans are presented in a clear Markdown protocol: rationale first, then a batch of actions for your approval. You review, approve, or reject — staying in control at every turn.

### 3. Local-First & Data Ownership

Your entire collaboration history lives on your machine in plain Markdown. No cloud lock-in. Your sessions are as portable, private, and versionable as the rest of your codebase.

### 4. Stateless & Transparent

Context goes in as a file, results come out as a file. Every turn is auditable. Agent personas are defined in simple XML files you can edit or create, making the workflow fully hackable.

## The TeDDy Workflow: Multi-Agent Development

TeDDy structures development around distinct AI agents, each with a specific mandate. Their interaction is mediated through documents, letting you steer the project at a high level.

<!-- Workflow diagram placeholder: `<img src="./assets/workflow-schematic.png" alt="TeDDy Workflow" />` -->

### 1. The Pathfinder (Strategic Discovery)
Navigates from a vague idea to a technically-grounded roadmap. Explores *why*, *what*, and *how*, then outputs a prioritized plan.

### 2. The Architect (System Design & Strategy)
Defines contracts, boundaries, and vertical slices. Uses spikes to de-risk uncertain approaches before committing to an architecture.

### 3. The Prototyper (De-risking)
Builds standalone scenario runners to validate uncertain feature slices before the Developer implements them.

### 4. The Developer (Outside-In TDD)
Implements features one deliverable at a time using a strict **Red-Green-Refactor** loop.

### 5. The Debugger (Scientific Fault Isolation)
Activated when other agents fail. Uses the scientific method to isolate root causes by building minimal reproduction cases.

### 6. The Assistant (General Purpose)
A flexible agent that follows your instructions without enforcing a strict process. Use it as a template for custom agents or for tasks that don't require the full disciplined workflow.

> Each agent's workflow is defined in plain-text XML files under `.teddy/prompts/` — you can customize any agent to fit your needs.

## The `teddy` CLI

The command-line tool that executes AI-generated plans on your filesystem.

### Getting Started

#### Prerequisites
- Python 3.11 or later.
- [uv](https://docs.astral.sh/uv/) — a fast Python package installer.

#### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Keep uv itself up-to-date:

```bash
uv self update
```

#### Install TeDDy

```bash
uv add teddy-cli
```

#### Initialize

```bash
teddy init
```

#### Add your API key

Edit `.teddy/config.yaml`:

```yaml
llm:
  api_key: "your-api-key-here"
```

#### Start a session

```bash
teddy start
```

Run with `--yolo` / `-y` for automatic approval:

```bash
teddy start -y
```

Resume a previous session:

```bash
teddy resume
```

#### Optional flags

- `--agent` / `-a` – Choose an agent persona (e.g., `pathfinder`, `architect`, `developer`).
- `--context` / `-c` – Pass additional context files or directories.
- `--model` / `-m` – Override the default model.

#### Browser chat usage

1. Run `teddy context` to copy your project context to the clipboard.
2. Paste it into an LLM chat interface alongside your request.
3. Have the model generate a Markdown plan.
4. Copy the plan and run `teddy execute` (or `teddy execute -y` for automatic execution).

### Upgrade

```bash
uv add teddy-cli
```

### Command Reference

| Command      | Description                                                               |
| ------------ | ------------------------------------------------------------------------- |
| `init`       | Initialize `.teddy` directory with defaults and pre-warm heavy imports.   |
| `start`      | Start an interactive session.                                             |
| `resume`     | Resume an existing session.                                               |
| `execute`    | Execute a Markdown plan. Reads from clipboard if no file path provided.   |
| `context`    | Gather project context (file tree + selected file contents) to clipboard. |
| `get-prompt` | Retrieve agent system prompts. Respects `.teddy/prompts/` overrides.      |

By default, `execute` and `context` copy their output to the clipboard. Use `--no-copy` to disable.

## Learn More

- [Project Roadmap & Vision](/docs/project/PROJECT.md)
- [System Architecture](/docs/architecture/ARCHITECTURE.md)
- [Agent Prompt Templates](/src/teddy_executor/resources/config/prompts/)
