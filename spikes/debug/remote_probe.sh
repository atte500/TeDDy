#!/bin/bash
echo "--- [DEBUG] Starting Polyglot Remote Probe ---"

echo "[RUNTIME: Bash]"
echo "Shell: $SHELL"
echo "Hostname: $(hostname)"

echo ""
echo "[RUNTIME: Python]"
poetry run python -c "import platform; import sys; print(f'Platform: {platform.system()} {platform.release()}'); print(f'Python: {sys.version}')"

echo "--- [DEBUG] Probe Logic Executed Successfully ---"