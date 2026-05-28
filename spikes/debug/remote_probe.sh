#!/bin/bash
# 1. Capture full help output to a file to avoid truncation in logs
poetry run teddy start --help > help_output.txt
echo "=== RAW HELP OUTPUT (HEX) ==="
head -c 1000 help_output.txt | xxd
echo "=== RAW HELP OUTPUT (TEXT) ==="
cat help_output.txt
echo "=== ENV VARS ==="
env | grep -E "TERM|COLOR|COLUMNS|LINES|CI"