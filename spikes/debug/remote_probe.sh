#!/bin/bash
echo "--- [DEBUG] Starting Polyglot Remote Probe ---"

echo "[RUNTIME: Bash]"
echo "Shell: $SHELL"
echo "Hostname: $(hostname)"

echo ""
echo "[RUNTIME: Python]"
poetry run python -c "import platform; import sys; print(f'Platform: {platform.system()} {platform.release()}'); print(f'Python: {sys.version}')"

echo ""
echo "[DIAGNOSTIC: Environment]"
if [ -z "$DATABASE_URL" ]; then
  echo "RESULT: DATABASE_URL is EMPTY or UNSET"
else
  echo "RESULT: DATABASE_URL is present (length: ${#DATABASE_URL})"
fi

echo "--- [DEBUG] Probe Logic Executed Successfully ---"