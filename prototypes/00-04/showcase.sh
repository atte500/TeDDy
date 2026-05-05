#!/bin/bash
# Prototype Showcase: Context Management UI
# This script launches an isolated TUI view to demonstrate token visibility and pruning.

export APP_ENV=prototype
export PROTOTYPE_SCENARIO=context_management

echo "Launching Context Management UI Prototype..."
python3 prototypes/00-04/tui_prototype.py