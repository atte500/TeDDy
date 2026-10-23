<div align="center">

<p align="center">
  <img src="https://raw.githubusercontent.com/atte500/teddy/main/assets/banner.png" alt="TeDDy: The opinionated software engineering harness - Because you should own the means of development" width="100%" style="max-width: 650px;" />
</p>

<p align="center">
  <a href="https://pypi.org/project/teddy-cli/"><img src="https://img.shields.io/pypi/v/teddy-cli?color=blue&style=flat-square" alt="PyPI version" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square" alt="Python 3.11+" /></a>
  <a href="https://github.com/atte500/teddy/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-purple.svg?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

```bash
uv tool install teddy-cli
```

<p align="center">
  <img src="https://raw.githubusercontent.com/atte500/teddy/main/assets/demo.gif" alt="TeDDy TUI Demo" width="100%" style="max-width: 100%; height: auto;" />
</p>

[Why TeDDy?](#why-not-just-use) &bull; [TeDDy's SDLC](#teddys-software-delivery-lifecycle) &bull; [Owning Your SDLC](#owning-your-sdlc) &bull; [Quickstart](#getting-started) &bull; [Usage](#usage) &bull; [FAQ](#frequently-asked-questions) &bull; [Support](#support)

</div>

---

## Motivation

The [2025 DORA report](https://dora.dev/research/2025/) found that AI adoption raises delivery throughput and product performance, but remains negatively related to delivery stability: code moves faster, but disproportionately more of it breaks. Any gains in raw speed are counterbalanced by increased effort needed for reviewing and reworking slop code to avoid technical defects and misalignment from compounding. Teams with fast feedback loops and loosely coupled systems see the most gain, while teams with inefficient processes and tight coupling see little or no benefit.

[Bain's 2026 Technology Report](https://www.bain.com/insights/the-missing-architecture-for-agentic-software-development-technology-report-2026/) reaches the same conclusion: AI has sped up coding, but that has shifted bottlenecks to review, governance, and software delivery. The limiting factor has shifted from the model to the connective architecture around it. Orchestrating and supervising AI agents is becoming an increasing part of software development at the expense of problem solving and critical thinking, which are being delegated to the machines. Better models will not by themselves fix the root causes of these structural issues.

TeDDy addresses them instead by embedding proven engineering practices like **[Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development), [Hexagonal Architecture](https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)), and [Iterative & Incremental Delivery](https://en.wikipedia.org/wiki/Iterative_and_incremental_development)** directly into the agentic workflow, using only local plain text files that you can read, review, and change, with nothing hidden in a proprietary database or cloud service.

---

## Video Walkthrough

<p align="center">
  <a href="https://www.youtube.com/watch?v=2j2fvRBGtag">
    <img src="https://images.weserv.nl/?url=https://img.youtube.com/vi/2j2fvRBGtag/maxresdefault.jpg&w=720&h=405&fit=cover" alt="Video Walkthrough" width="650" />
    <br>
    <img src="https://img.shields.io/badge/YouTube-Watch%20Here-red?style=for-the-badge&logo=youtube" alt="Watch on YouTube" /><br/><br/>
  </a>
</p>

---

## Why Not Just Use...

<details>
<summary><strong>...Skill.md files?</strong></summary>

<br />

Skills are designed for task-specific procedures, but stretching them to manage the entire software delivery lifecycle quickly becomes unmaintainable. Because they sit on top of your harness's built-in system prompt, upstream updates will often alter that base prompt without warning, introducing subtle conflicts or workflow drift over time. TeDDy instead organizes the full [SDLC](#teddys-software-delivery-lifecycle) across specialized agents, where each follows a process structured into phases and concrete steps via dedicated system prompts that you fully control. Your existing skill files can still be passed to these agents as context for the task-specific jobs they were built for.

</details>

<details>
<summary><strong>...Spec-driven development?</strong></summary>

<br />

Spec-driven development requires you to define everything upfront before writing code. This is essentially the [waterfall model](https://en.wikipedia.org/wiki/Waterfall_model) under a new name, relying on the assumption that initial requirements will be completely accurate. That assumption rarely holds, as non-trivial systems always uncover edge cases and evolving requirements during development. TeDDy still uses specifications, but treats them as living documents within an iterative process more akin to [Agile](https://en.wikipedia.org/wiki/Agile_software_development), allowing the design to adapt as you build.

</details>

<details>
<summary><strong>...Automation?</strong></summary>

<br />

TeDDy integrates automated pre-commit hooks, local test suites, and CI/CD pipelines directly into the agent workflow. Even so, automated tests alone cannot prevent misalignment or verify intent. As [Bain's report](https://www.bain.com/insights/the-missing-architecture-for-agentic-software-development-technology-report-2026/) notes, speeding up code generation without redesigning the surrounding process does not compound gains; it just redistributes the pain to the slowest human checkpoint. TeDDy pairs these automated quality gates with a human-in-the-loop workflow mediated through specific Markdown documents across each phase of the [software delivery lifecycle](#teddys-software-delivery-lifecycle).

</details>

---

## What Makes TeDDy Special

1. **Markdown as the interface.** Inspired by [Obsidian](https://obsidian.md/), living documents such as specs, architecture contracts, and vertical slices mediate every part of the [SDLC](#teddys-software-delivery-lifecycle). All agent responses and tool calls are also plain Markdown, fully controllable via the built-in TUI while leveraging your native editor instead of restricting the means of development to a chat window.
2. **Local-first architecture.** Inspired by the [UNIX philosophy](https://en.wikipedia.org/wiki/Unix_philosophy) of small, sharp tools, TeDDy runs entirely inside your existing workspace with no cloud dependencies, proprietary databases, or background telemetry. It integrates cleanly with standard developer environments, allowing your terminal, local Git hooks, and preferred editor to drive the workflow.
3. **Auditable by design.** Inspired by [Git](https://git-scm.com/)'s ledger model, every session maintains an immutable history of what the agent intended and what actually executed. Each plan enforces a structured rationale covering synthesis, justification, and expected outcomes, making agent reasoning fully traceable, searchable, and easy to parse with your own scripts for analysis.

---

## Why Working Code Is Not Enough

LLMs are pre-trained on next-token prediction and fine-tuned with reinforcement learning to solve discrete and well-defined tasks, making them effective at writing code that works in isolation, but poorly equipped to navigate uncertainty or keep code and intent aligned over time. LLMs are also evaluated and trained on generating the final solution in one shot instead of working iteratively and incrementally, which, if left unchecked, leads to defects compounding on top of each other over time.

Defects in software come in two kinds: technical defects, where <u>code matches your intent but breaks on edge cases or introduces bugs</u>, and misalignment, where the <u>code technically works but is not what you actually wanted</u>. Most coding harnesses do little to address either one, forcing teams to patch extra tools and components into their software development lifecycle just to keep code on track. TeDDy instead tackles both types of defects directly within the harness, preventing them before they happen and mitigating them as early as possible when they do.

For **technical defects**, TeDDy prevents structural failures through Design by Contract, enforcing Hexagonal Architecture through ports and adapters. To mitigate bugs during development, it uses a strict Test-Driven (Red-Green-Refactor) cycle to write tests first and commit code in small units to surface errors early.

For **misalignment**, TeDDy prevents building the wrong thing by using spikes and prototypes to de-risk uncertain solutions before committing to an architecture. During implementation, it mitigates drift by delivering features through small vertical slices. Specific Markdown documents mediate every phase transition, anchoring the agents and providing a high-level steering interface to keep humans in the loop.

<p align="center">
  <img src="https://raw.githubusercontent.com/atte500/teddy/main/assets/matrix.png" alt="Workflow Matrix" width="100%" />
</p>

---

## TeDDy's Software Delivery Lifecycle

Instead of winging the process on the go or taking the shortest path to generate code, agents follow a structured delivery process mediated by plain Markdown documents:

<p align="center">
  <img src="https://raw.githubusercontent.com/atte500/teddy/main/assets/workflow-schematic.png" alt="TeDDy Workflow" width="100%" />
</p>

1. **Strategic Alignment & Roadmapping:** The **Pathfinder** aligns incoming requests with the product vision, roadmap, and permanent system invariant specifications.
2. **Contract-First Architecture:** The **Architect** enforces Ports & Adapters boundaries, drafts component contracts, and decomposes milestones into vertical slices that deliver complete end-to-end functionality across all layers.
3. **Sandbox De-Risking:** The **Prototyper** conducts isolated [spikes](https://en.wikipedia.org/wiki/Spike_(software_development)) to de-risk technical and functional unknowns before any production code is touched.
4. **Atomic Test-Driven Delivery:** The **Developer** implements vertical slices through test-driven (Red-Green-Refactor) cycles, committing one atomic deliverable at a time to maintain a continuous green state.
5. **Empirical Diagnostics:** When bugs or regressions occur, the **Debugger** isolates root causes using Minimal Reproducible Examples (MREs) and validates fixes against isolated replicas before touching production code.
6. **Automated Quality Gates & CI/CD:** Local pre-commit hooks catch formatting, secret, and merge issues on staged files, while continuous integration automatically validates test suites and quality checks across platforms.
7. **Tactical Chores:** The **Assistant** handles one-off scripts, simple refactors, and ad-hoc maintenance through a fast feedback loop without heavy ceremonial overhead.

---

## Owning Your SDLC

TeDDy is built on the belief that you should own your software delivery lifecycle. Even though TeDDy comes with opinionated defaults handcrafted from my own engineering preferences and daily development experience, every part of the process is designed to be easily tailored to your team's workflow without touching any application code:

- **High-Level Governance Rules (`PROJECT.md` & `ARCHITECTURE.md`):** The simplest way to guide agents. Define product roadmaps, engineering principles, system laws, and component boundaries in living Markdown documents that agents read on every turn.
- **Artifact Templates (`docs/templates/`):** Standardize the artifacts produced during development. Customize the Markdown templates for vertical slices, specifications, case files, and milestones to match your documentation standards.
- **Agent Prompts (`.teddy/prompts/`):** To change the process itself, customize the agent prompts. Each agent's workflow is broken down into structured phases and individual steps, defined entirely in Markdown. You can tweak instructions, add domain-specific quality gates, or introduce brand-new agent personas to match how your team builds software. TeDDy composes each system prompt from the agent's instructions plus a shared response protocol it appends automatically. The composed prompt is saved in the session folder. You can also run `teddy get-prompt <agent>` to retrieve it without starting a session. A customized prompt that already includes `<response_format>` opts out of the shared protocol.
- **Command Automation (`Makefile`):** Instead of hardcoding shell commands inside agent prompts, common development and verification operations are routed through the Makefile. When you need to change a flag, runner, or environment setup, you change it once in the Makefile instead of updating instructions across multiple agent prompts.
- **Context Filtering (`.teddyignore`):** Control which files TeDDy scans during context generation and tree traversal. A `.teddyignore` file in the project root follows standard ignore syntax and takes precedence over `.gitignore`, allowing you to ignore extra paths or re-include git-ignored files using negation patterns.

> [!TIP]
> *Interested in bringing TeDDy into your team or designing custom agent workflows?* <br>
> **[Professional consulting is available!](#support)**

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- `uv` (recommended) or `pip` (included with Python)

### Install TeDDy

```bash
uv tool install teddy-cli
```

### Installing Experimental Versions

To install or upgrade to the latest development pre-release directly from PyPI:

```bash
uv tool install teddy-cli --pre --force
```

> [!WARNING]
> Experimental versions are published as PEP 440 dev pre-releases on PyPI and may include breaking changes or unstable features.

### Initialize

```bash
teddy init
```

Use subcommands to overwrite specific defaults:

- `teddy init prompts`: Overwrite bundled prompt Markdown files in `.teddy/prompts/` (useful after upgrades).
- `teddy init config`: Overwrite `config.yaml`, `.gitignore`, and `init.context` with defaults. Preserves existing `.env` files.
- `teddy init templates`: Overwrite bundled Markdown templates in `docs/templates/` with defaults.

### Configuration

The first execution of `teddy start` runs an interactive setup to configure your API key and preferred editor. For deeper customization, edit `.teddy/config.yaml`. All `llm.*` settings pass directly through to [LiteLLM](https://docs.litellm.ai/docs/completion/input), allowing you to route to cloud providers or local endpoints (Ollama, llama.cpp, or any OpenAI-compatible server via `api_base`). The config file also lets you adjust your external editor, command execution timeouts, diff similarity thresholds, and automated context pruning budgets.

### Environment Variables

TeDDy checks the following process environment variables at startup and during a session.

| Variable                 | Purpose                                                                                                                                                     |
| :----------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TEDDY_LLM_API_KEY`      | The LLM API key. The bundled `config.yaml` default references it as `llm.api_key: "${TEDDY_LLM_API_KEY}"`. A shell value wins over the `.teddy/.env` value. |
| `EDITOR`                 | Fallback editor command when `editor` is unset in `.teddy/config.yaml`.                                                                                     |
| `TEDDY_DIFF_TOOL`        | Overrides the auto-detected diff viewer.                                                                                                                    |
| `TEDDY_MAX_TURNS`        | Overrides the maximum number of turns for a non-interactive run.                                                                                            |
| `TEDDY_MAX_SESSION_COST` | Overrides the maximum session cost in dollars for a non-interactive run.                                                                                    |

TeDDy also interpolates any `${VAR}` or `${VAR:-default}` token in `.teddy/config.yaml` against `.teddy/.env` layered under the process environment, so you can reference your own secrets from config values.

### Using TeDDy in CI

TeDDy is safe to run in non-interactive environments. When stdin is not a terminal, TeDDy skips the API-key and editor setup prompts automatically, so no command blocks waiting for input.

To run TeDDy in a pipeline, set `TEDDY_LLM_API_KEY` in the environment and pass `--pipeline` (`-p`), which auto-approves actions, requires `-m`, exits after the first message turn, and defaults to the `assistant` agent.

```bash
TEDDY_LLM_API_KEY="$OPENROUTER_API_KEY" teddy start --pipeline -m "do the thing"
```

---

## Usage

### Starting and Resuming Sessions

```bash
# Start an interactive session (defaults to Pathfinder)
teddy start

# Start with automatic action approval (non-interactive)
teddy start -y

# Start with a specific agent and prompt
teddy start -a architect -m "Plan the auth module"

# Resume the most recent session
teddy resume

# Resume a specific session by slug or path
teddy resume my-feature-branch
teddy resume .teddy/sessions/20260825_151900-my-feature-branch

# Resume an ongoing session with a different agent persona
teddy resume -a developer
```

Interrupt a running session with `q` or `Ctrl+C` at any time. The action currently in flight will stop immediately, remaining actions will be skipped, and the report will be written to preserve the audit trail.

Resume with additional instructions:

```bash
teddy resume -m "your next instruction"
```

### Optional Flags

| Flag                            | Description                                                                                                                                   |
| :------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| <nobr>`--agent`, `-a`</nobr>    | Select agent persona (`pathfinder`, `architect`, `developer`, `debugger`, `assistant`). Default: `pathfinder` (`assistant` in pipeline mode). |
| <nobr>`--context`, `-c`</nobr>  | Supply additional context files or directories. Repeatable (`-c a.py -c b.md`) or comma-separated (`-c "a.py,b.md"`).                         |
| <nobr>`--model`</nobr>          | Override the default configured model.                                                                                                        |
| <nobr>`--yolo`, `-y`</nobr>     | Auto-approve all actions. To make this default, set `yolo_default: true` in `.teddy/config.yaml`.                                             |
| <nobr>`--no-yolo`, `-n`</nobr>  | Force interactive mode for a single run.                                                                                                      |
| <nobr>`--message`, `-m`</nobr>  | Initial instruction to pass directly to the agent.                                                                                            |
| <nobr>`--pipeline`, `-p`</nobr> | Pipeline mode. Auto-approves actions, requires `-m`, exits immediately after the first message turn, and defaults to the `assistant` agent.   |
| <nobr>`--max-turns`</nobr>      | Maximum turns for a non-interactive run. Overrides `guardrails.max_turns` in `.teddy/config.yaml`.                                            |
| <nobr>`--max-cost`</nobr>       | Maximum session cost in dollars for a non-interactive run. Overrides `guardrails.max_session_cost` in `.teddy/config.yaml`.                   |

### Chat-Oriented Workflow (CHOP)

You do not need API keys or per-token billing to use TeDDy. If you already have an active subscription (ChatGPT, Claude, Gemini, etc.), you can also use TeDDy to practice **[Chat-Oriented Programming (CHOP)](https://arxiv.org/html/2510.10819v1#S2.2)** from your web browser.

TeDDy packages your workspace context into a single clipboard payload, and the agent prompts instruct the model to automatically format its response as an executable, self-contained Markdown plan.

1. **Set the system instructions:** Copy your chosen agent persona's prompt with `teddy get-prompt <agent_name>` and paste it into your web interface's system prompt or custom instructions field.
2. **Bundle project context:** Export your workspace context to the clipboard with `teddy context` (see [Exporting Context](#exporting-context)). This bundles system information, current git status, project structure, and the full verbatim contents of all files listed in `.teddy/init.context` into a single Markdown payload.
3. **Prompt the AI:** Paste the context payload into the chat alongside your task request. Guided by the system instructions, the model will automatically structure its response as an executable Markdown plan.
4. **Apply changes:** Copy the full Markdown plan to your clipboard and run `teddy execute` to validate, review diffs, and apply approved changes automatically, or copy and run individual snippets manually as you would in standard CHOP.
5. **Report back:** When `teddy execute` finishes, it automatically copies a concise execution report back to your clipboard to paste into the chat.

### Exporting Context

`teddy context` bundles system information, git status, project structure, and file contents into a single Markdown payload. It copies the payload to the clipboard unless you pass `--no-copy`.

Pass `-c/--context` to add ad-hoc values for a single run. The flag is repeatable and accepts comma-separated values. Explicit values extend the default set from `.teddy/init.context`. They do not replace it.

```bash
# Add two files beside the default init.context entries
teddy context -c README.md -c src/app.py

# Comma-separated values expand to separate entries
teddy context -c "README.md,pyproject.toml"

# Export only the chosen files and skip the default set
teddy context --only -c README.md
```

A `-c` value resolves by kind. A directory expands recursively. A URL is fetched instead of resolved on disk. A file named `<name>.context` is treated as a manifest: the command reads one path per line, skips blank lines and `#` comments, and expands each entry. Any other file is embedded verbatim.

```bash
teddy context -c review.context
```

`--only` requires at least one `-c` value. Without one the command exits with a usage error, because an empty explicit set would export no files.

---

## Command Reference

| Command                       | Description                                                                                                                              |
| :---------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------- |
| `init`                        | Initialize `.teddy` workspace with defaults and pre-warm dependencies.                                                                   |
| <nobr>`init prompts`</nobr>   | Overwrite bundled prompt Markdown files in `.teddy/prompts/` with defaults.                                                              |
| <nobr>`init config`</nobr>    | Overwrite `config.yaml`, `.gitignore`, and `init.context` with defaults.                                                                 |
| <nobr>`init templates`</nobr> | Overwrite bundled Markdown templates in `docs/templates/` with defaults.                                                                 |
| `start`                       | Start an interactive agent session.                                                                                                      |
| `resume`                      | Resume an existing session.                                                                                                              |
| `update`                      | Check for updates and display upgrade instructions.                                                                                      |
| `execute`                     | Execute a Markdown plan (reads from clipboard if no path is provided).                                                                   |
| `context`                     | Export context payload (system info, git status, file tree, `init.context`). Add ad-hoc files with `-c` and skip defaults with `--only`. |
| <nobr>`get-prompt`</nobr>     | Output the composed system prompt (agent instructions plus the shared response protocol).                                                |

> [!NOTE]
> By default, `execute` and `context` copy output to the clipboard. Use `--no-copy` to bypass.

---

## Frequently Asked Questions

<details>
<summary><strong>Does TeDDy collect telemetry or phone home?</strong></summary>

<br />

No. TeDDy collects zero telemetry, zero analytics, and runs no background tracking. All requests go directly to whichever LLM provider or local endpoint you configure in your local config file.

By default, OpenRouter requests include attribution headers (`HTTP-Referer` and `X-OpenRouter-Title`) to credit usage to TeDDy on OpenRouter rankings. Set `llm.extra_headers: null` in `.teddy/config.yaml` to opt out. Other providers ignore these headers.

</details>

<details>
<summary><strong>Which models and providers are supported?</strong></summary>

<br />

TeDDy uses [LiteLLM](https://docs.litellm.ai/) under the hood. You can route to any provider supported by LiteLLM, including OpenRouter, Anthropic, OpenAI, and Google Gemini. For local models, it supports Ollama, vLLM, LM Studio, llama.cpp, and any OpenAI-compatible endpoint.

</details>

<details>
<summary><strong>Do I need to migrate my existing codebase to use this?</strong></summary>

<br />

No. TeDDy is designed to run inside existing repositories. It only creates a `.teddy/` directory in your project root to hold prompts, configuration, and session history.

</details>

<details>
<summary><strong>How do teams collaborate with TeDDy?</strong></summary>

<br />

All strategic artifacts created by agents (roadmaps in `docs/project/`, component designs, and vertical slices) are saved directly in your repository's `docs/` directory and committed to Git like regular code. The internal `.teddy/` directory is ignored by default, keeping private session logs and environment credentials local to each developer.

</details>

<details>
<summary><strong>Are there hidden fees? How is TeDDy licensed and monetized?</strong></summary>

<br />

There are no subscriptions, hidden fees, or token markups. You bring your own API keys or local models and pay providers directly at standard rates with zero middleman.

TeDDy is completely free software under the AGPL-3.0 license. As a copyleft license, if you modify and distribute TeDDy itself, your changes must also be open-sourced under the AGPL. However, using TeDDy as a development harness to write your own software does not affect your codebase; you fully own all code generated by the agents under whatever license you choose.

The tool itself is not monetized. If your team needs custom agent architectures, workflow design, or dedicated onboarding support, professional consulting is available at [raphael@atteritano.ch](mailto:raphael@atteritano.ch).

</details>

---

## Learn More

- [Project Roadmap & Vision](https://github.com/atte500/teddy/blob/main/docs/project/PROJECT.md)
- [System Architecture](https://github.com/atte500/teddy/blob/main/docs/architecture/ARCHITECTURE.md)
- [Agent Prompt Templates](https://github.com/atte500/teddy/tree/main/src/teddy_executor/resources/config/prompts)

---

<div align="center" id="support">

### Support

If you find TeDDy useful, consider giving it a star!

<p align="center">
  <a href="https://github.com/atte500/teddy"><img src="https://img.shields.io/github/stars/atte500/teddy?style=flat-square&logo=github&label=Star%20TeDDy" alt="GitHub stars" /></a>
  <a href="https://www.youtube.com/@xCogito-tv"><img src="https://img.shields.io/badge/YouTube-@xCogito--tv-red?style=flat-square&logo=youtube" alt="YouTube" /></a>
  <a href="mailto:raphael@atteritano.ch"><img src="https://img.shields.io/badge/Email-raphael%40atteritano.ch-blue?style=flat-square&logo=gmail" alt="Email" /></a>
</p>

</div>
