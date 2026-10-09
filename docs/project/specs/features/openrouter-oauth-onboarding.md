# Spec: Frictionless Onboarding via OpenRouter OAuth & Sponsorship Funnel

- **Status:** Active
- **Created Date:** 2026-05-20
- **Updated Date:** 2026-10-09

## 1. Overview / Problem Statement

### The Goal
Provide a zero-friction, one-click onboarding experience for TeDDy users through automated authentication while establishing a clean, non-intrusive funnel to support the open-source project via GitHub Sponsors.

### The Friction
Currently, getting started with TeDDy requires users to manually obtain and configure raw provider API keys (OpenAI, Anthropic, or OpenRouter) in `.teddy/config.yaml` or `.teddy/.env`. This manual key management creates immediate drop-off for new users and increases the risk of accidental secret exposure.

### The Solution
Integrate **OpenRouter OAuth (PKCE)** alongside a **GitHub Sponsors** patron funnel:
1. **Zero-Configuration Key Provisioning:** Users authenticate with their OpenRouter account via `teddy login` (or automated first-run preflight). OpenRouter mints a user-scoped API key returned directly to the CLI over a local PKCE callback—no API keys are ever copy-pasted.
2. **Universal Model Access:** Users can immediately run any frontier model (Claude 3.5 Sonnet, GPT-4o, DeepSeek, etc.) without multi-provider setup.
3. **Transparent Sponsorship Support:** Use respectful GitHub Sponsors prompt at session initialization, encouraging developers and teams using TeDDy to sustain development directly.

---

## 2. Key Architectural & Product Questions

### Persistence & OAuth Lifecycle
- **Single-Login Persistence:** Users authenticate once. API keys provisioned via OpenRouter PKCE do not expire unless revoked by the user in their OpenRouter dashboard.
- **Silent Reuse:** The retrieved key is persisted to `.teddy/.env`. TeDDy detects and reuses this key automatically across all commands (`start`, `resume`, `plan`, `execute`). The user does not need to re-authenticate on the same machine.

### Secure Secret Storage & BYOK
- **Separation of Concerns:**
  1. **System Environment Variables:** TeDDy resolves environment variables with top priority.
  2. **Dedicated Credentials File:** The OAuth flow writes its key to `.teddy/.env`. This file is strictly excluded from version control via the default `.teddy/.gitignore` template.
  3. **Clean Configuration File:** `.teddy/config.yaml` holds non-sensitive preferences (model aliases, editor commands, auto-approval flags).

---

## 3. Guiding Principles / Core Logic

- **First-Class BYOK:** Bring Your Own Key remains fully supported. If a user defines standard environment variables or manual keys in `.teddy/.env`, TeDDy runs directly with no interference.
- **Leaderboard Attribution:** All requests routed through OpenRouter include standard attribution headers (`HTTP-Referer: https://github.com/raphaelatteritano/TeDDy` and `X-Title: TeDDy CLI`) to contribute to OpenRouter rankings and ecosystem visibility.
- **Respectful Sponsorship Prompting:** TeDDy will display a single, non-spammy unicode/color terminal message *only on new session initialization* thanking the user and inviting them to sponsor development on GitHub Sponsors. No emojis are used.
