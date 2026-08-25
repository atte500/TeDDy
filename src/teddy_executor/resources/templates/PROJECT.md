# Project: {{project_name}}

## Product Vision
The overarching goals, target audience, unique value proposition, and major future directions for the product.

**Format:** 2-3 paragraphs describing the product's mission, target users, and what makes it unique.

## Guiding Principles
Core engineering philosophy, quality standards, and foundational rules that dictate how the team builds software.

**Format:** Bulleted list. Each entry: `N. **Principle Name:** Description and how it applies to daily work.`

## Workflow Standards
Defines the high-level artifact lifecycle and conventions for project management documents.

**Format:** Bulleted list. Each entry defines a specific standard.

### Required Topics:
- **Artifact Lifecycle:** How work flows (e.g., Spec → Milestone → Slice).
- **Numbering:** Sequential MM-NN format, 00 prefix for ad-hoc work.
- **Archiving Policy:** When and how completed artifacts are archived or deleted.

## Roadmap

**Mandatory Prerequisites:** Milestone 0 (Project Bootstrapping) is a required standard that MUST be completed before any feature work begins. It establishes the foundational infrastructure — testing framework, CI/CD pipeline, pre-commit hooks, post-commit test gate, and Makefile — that all subsequent milestones depend upon. No feature work may proceed until these foundations are in place.

A living list of upcoming Milestones and their high-level features.

**Template format:**

```
### Milestone N: [Name] [STATUS]
- **Core Goal:** [High-level objective]
- **Specs:** [Link to Specification Document(s)]
- **Requirements:
    - Requirement 1
    - Requirement 2
```

### Milestone 0: Project Bootstrapping [PLANNED]
- **Core Goal:** Establish the foundational project infrastructure for testing, CI/CD, and pre-commit quality gates.
- **Specs:** N/A — Milestone 0 is self-defining.
- **Requirements:**
    - **Testing Framework Setup:** Configure the project's designated test runner (e.g., `pytest`) with test discovery conventions.
    - **CI/CD Pipeline:** Set up two parallel jobs: 1) Blocking OS matrix test suite with coverage targets. 2) Non-blocking quality checks (formatters, linters, security scanners).
    - **Pre-commit Hooks:** Install the Pre-commit framework with hooks for formatters, linters, security scanners.
    - **Post-commit Hook:** Implement a hook that runs the full test suite and reverts on failure.
    - **Makefile:** Create a `Makefile` following [docs/templates/makefile.md](docs/templates/makefile.md) with `make commit` and `make probe` commands.

## Technical Debt
Tracks known technical debt for future cleanup.

**Format:** `- [Description including context and location of the debt item.]`

**Deletion Policy:** When a technical debt item is addressed (the underlying issue is resolved in a completed milestone/slice), the entry MUST be deleted from this section. Do not mark it as "completed" or "resolved" — remove it entirely. Git history serves as the permanent record.
