#!/bin/bash
# Integrated Showcase: Context Management UI
# This script launches the ACTUAL teddy CLI with prototype-only features enabled via guards.

export APP_ENV=prototype
export PROTOTYPE_SCENARIO=context_management
export TEDDY_UI_MODE=tui

# We use a dummy plan to trigger the reviewer
cat <<EOF > .tmp_plan.md
# Slice: Integrated Showcase
- Status: Planned
- Agent: Prototyper

## Rationale
~~~~~~
1. Synthesis
Testing integration of the Context Management UI.
~~~~~~

## Action Plan
### EXECUTE
- Description: Integrated Prototype Action
~~~~~~shell
echo "Integrated Prototype"
~~~~~~
EOF

echo "Launching Integrated Context Management UI..."
poetry run teddy execute .tmp_plan.md

rm .tmp_plan.md