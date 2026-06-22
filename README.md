# TeDDy: A Coding Harness Designed for Quality

<!-- Old video placeholder – will be updated with new release video
[![My Plan to Fix AI Coding](https://img.youtube.com/vi/By6wGuT-4sA/0.jpg)](https://www.youtube.com/watch?v=By6wGuT-4sA)
-->

As developers we've come to accept the premise that working with AI is inherently going to produce low-quality code. People seem to either accept it as a trade-off for speed, or they avoid using it for that exact reason. I believe it doesn't have to be that way.

TeDDy is a radically different coding harness that uses **Markdown as Interface** and directly embeds proven software engineering practices like **Test-Driven Development, Hexagonal Architecture, and iterative delivery**. 

## Why LMMs Suck at Software Development

At its core, an AI agent is a language model paired with a harness. LLMs are trained for next-token prediction and optimized for short-term, atomic tasks. They naturally try to generate the final solution in one shot, which makes the defects they introduce compound turn after turn.

Addessing and preventing defects has been a central problem for software engineering long before LLMs became a thing. So maybe we should take a page out of real software engineering practices, that have been proven over decades and apply them to AI-assisted software development as well.

We can conceptually split **defects in software** into two categories:

- **Technical**: code that simply doesn't work the way it's intended.
- **Misalignment**: code that technically works but isn't what the user(s) actually wanted.

Current coding harnesses don't address these issues at all and frontier models are also hitting diminishing returns, leaving users trying to fix these by bolting on external systems like MCPs, skill files and spec-driven development, leading to a messy and frustrating development experience.

TeDDy instead attempts to solve these issues directly by adopting, amongst others, the following strategies:
- **For Technical Defects:** TeDDy enforces a strict **Test-Driven (Red-Green-Refactor)** cycle. The AI must write a test first and verify it fails before writing any actual code. This catches errors early, before they compound.
- **For Misalignment:** Instead of specing everything upfront and building layer by layer, TeDDy builds features as **end-to-end vertical slices**. Each slice gives you a working piece of software to review and verify alignment.

**Additionally:** The use of Pre-commit quality checks and post-commit test suite run is designed to prevent defective code to reach your repo, allowing multiple agents to work in parallel while ensuring continuous integration.

## Guiding Principles

1. **Markdown as Interface:** Each turn the LLM is made to follow a human-friendly Markdown protocol, including first a rationale for the plan and then a batch of actions to be executed that turn. Allowing you to review, approve, or reject each step while staying in control at every turn. The approven actions from the Markdown response are parsed and executed directly by the harness without requiring a separate JSON / YAML format for it.
2. **Data Ownership:** Your entire collaboration history lives on your machine in plain Markdown. There is inherently no cloud lock-in, and local models are also fully supported. Your sessions are as portable, private, and versionable as the rest of your codebase.
3. **Fully Hackable:** Context goes in as a file, responses come out as a file. Every turn is completely auditable and human-friendly. Agents are defined in plain-text files meaning you can edit or create new agents to tailor the workflow to your needs.

## The TeDDy Workflow

TeDDy breaks down the development process into distinct agents, each with a specific mandate. Their interaction is mediated through documents, letting you steer the project at a high level throughout.

<img src="./assets/workflow-schematic.png" alt="TeDDy Workflow" />

1. **Pathfinder:** Navigates from a vague idea to a technically-grounded roadmap. Explores *why*, *what*, and *how*, then helps you concretize it into a plan.
2. **Architect:** Defines contracts, boundaries, and vertical slices for the Developer. Uses spikes to de-risk uncertain approaches before committing to an architecture.
3. **Prototyper:** Builds standalone prototype to validate uncertain features before the Developer implements them.
4. **Developer:** Implements features one deliverable at a time using a strict **Red-Green-Refactor** loop.
5. **Debugger:** Uses the scientific method to isolate root causes by building minimal reproduction cases.
6. **Assistant:** A flexible agent that follows your instructions without enforcing a strict process. Use it as a template for custom agents or for tasks that don't require the full disciplined workflow.

> **Note:** Each agent's workflow is defined in plain-text XML files under `.teddy/prompts/`. You can customize any agent to fit your needs or create new ones for specific uses cases.

## Getting Started

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

#### LLM Configuration

Edit `.teddy/config.yaml`:

```yaml
llm:
  api_key: "your-openrouter-api-key-here"
  model: "openrouter/deepseek/deepseek-v4-flash:nitro"
```

> **Note:** You can update the `model` field to switch providers/models. TeDDy defaults to the [OpenRouter API](https://openrouter.ai/) which supports hundreds of models. To change the model, simply edit the `model` value in your config.

#### Editor Configuration

Set your preferred editor for reviewing and modifying plans:

```yaml
editor: "nvim"
```

If no editor is configured, TeDDy will use the system default. Supported editors include `nvim`, `vim`, `code`, and any editor available on your `PATH`.

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
