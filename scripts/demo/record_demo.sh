#!/usr/bin/env bash
# Autonomously record the interactive TeDDy showcase demo to assets/demo.gif.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
DEMO_DIR="$REPO_ROOT/scripts/demo"
WORK="$(mktemp -d)"
PORT="${FAKE_LLM_PORT:-8124}"

export FAKE_LLM_PORT="$PORT"
export FAKE_LLM_STATE="$WORK/fake_state"
export FAKE_LLM_LOG="$WORK/fake_llm.log"
export FAKE_LLM_DELAY_MIN="2.2"
export FAKE_LLM_DELAY_MAX="3.2"
export WORK_DIR="$WORK"
export REPO_ROOT
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"
export PYTHONUTF8="1"
export PROMPT_TOOLKIT_NO_CPR="1"
unset VIRTUAL_ENV

cleanup() { kill "${FAKE_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT

install_if_missing() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Installing $1 via Homebrew..."
    HOMEBREW_NO_AUTO_UPDATE=1 brew install "$1"
  fi
}
install_if_missing asciinema
install_if_missing agg

# Fake, keyless model.
python3 "$DEMO_DIR/fake_llm.py" >"$WORK/fake_llm.stdout" 2>&1 &
FAKE_PID=$!
sleep 1

# Throwaway project pointed at the fake model.
cd "$WORK"
git init -q
git config user.email demo@teddy.local
git config user.name "TeDDy Demo"
echo "# Demo Project" > README.md
git add -A && git commit -qm init
mkdir -p .teddy
cat > .teddy/config.yaml <<EOF
editor: "nvim"
checks:
  prompts: false
  templates: false
  update: false
llm:
  model: "deepseek/deepseek-v4.1-flash"
  api_key: "sk-fake"
  api_base: "http://127.0.0.1:$PORT/v1"
EOF

export PATH="$(dirname "$(command -v uv)"):$PATH"

# Pre-warm uv dependencies outside the recording so no resolution messages appear in the GIF
uv run --project "$REPO_ROOT" --with pexpect python -c "import pexpect; print('ready')" >/dev/null 2>&1 || true

# Record the interactive session with matching terminal geometry
asciinema rec --overwrite --window-size 150x26 --command "uv run --project '$REPO_ROOT' --with pexpect python $DEMO_DIR/drive.py" "$WORK/demo.cast"
mkdir -p "$REPO_ROOT/assets"
agg --cols 150 --rows 26 --speed 1 "$WORK/demo.cast" "$REPO_ROOT/assets/demo.gif"

echo "=== demo recorded to assets/demo.gif ==="
