# Spec: {{invariant}}
- **Status:** Active

> **Scope:** This template codifies **permanent system invariants** only — stable formats, contracts, protocols (e.g. the MRP), core data models, and non-negotiable architectural rules of record. It is NOT for feature goals, requirements, or acceptance criteria; those belong in Milestone documents (`docs/project/milestones/`) and Vertical Slices.

## Overview / Problem Statement

**Format:** 2-3 paragraphs describing the invariant being codified, why it exists, and what it guarantees.
Context for the invariant, the contract it establishes, and the risk it mitigates.

## Guiding Principles / Core Logic

**Format:** Bulleted list. Each entry: `- **Principle:** Description and how it constrains design decisions.`
Foundational rules, engineering philosophy, or logical constraints.

## Technical Specification

**Format:** Use sub-sections as needed. Include:
- Data models / contracts (tables or code blocks)
- File paths and directory structures
- Workflow diagrams (Mermaid) where applicable
- Algorithm descriptions
- Configuration options
Detailed logic, file formats, directory structures, or workflow diagrams (Mermaid).

## Guidelines

**Format:** Bulleted or numbered list of rules for conforming to and evolving this invariant. Each entry should constrain design decisions, not prescribe specific implementation.
Conformance requirements and the process for amending the invariant.
