#!/bin/bash
echo "##[group]remote_probe"
echo "--- Remote Environment State ---"
echo "User: $(whoami)"
echo "PWD: $(pwd)"
echo "Node Version: $(node -v 2>/dev/null || echo 'not installed')"
echo "Python Version: $(python --version 2>/dev/null || echo 'not installed')"

echo "Checking API_KEY presence..."
if [ -z "$API_KEY" ]; then
  echo "RESULT: API_KEY is EMPTY or UNSET"
else
  echo "RESULT: API_KEY is SET (length: ${#API_KEY})"
fi

echo "Checking DATABASE_URL (provided by debug.yml)..."
if [ -z "$DATABASE_URL" ]; then
  echo "RESULT: DATABASE_URL is EMPTY or UNSET"
else
  echo "RESULT: DATABASE_URL is SET (length: ${#DATABASE_URL})"
fi

echo "--- File System Check ---"
ls -la
echo "##[endgroup]"