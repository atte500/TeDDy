#!/usr/bin/env python3
"""
MRE: Reproduce trafilatura's "discarding data: None" warning.

Demonstrates that calling trafilatura.extract() without passing a `url`
parameter results in the log message "discarding data: None" when extraction fails.
"""
import logging
import sys
import trafilatura

# Capture trafilatura's log output
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s | %(name)s | %(message)s",
    stream=sys.stderr,
)

# Scenario 1: Empty content, no URL → "discarding data: None"
print("=== Scenario 1: Empty content, no URL ===", file=sys.stderr)
result1 = trafilatura.extract(
    "",
    output_format="markdown",
    include_links=True,
    include_formatting=True,
)
print(f"Result: {result1!r}", file=sys.stderr)

print(file=sys.stderr)

# Scenario 2: Valid content, valid URL → should succeed or show URL in log
print("=== Scenario 2: Valid content with URL ===", file=sys.stderr)
result2 = trafilatura.extract(
    "<html><body><p>Hello, world!</p></body></html>",
    url="https://example.com/test-page",
    output_format="markdown",
    include_links=True,
    include_formatting=True,
)
print(f"Result: {result2!r}", file=sys.stderr)

print(file=sys.stderr)

# Scenario 3: Invalid content (too short for trafilatura's min_output_size)
# but WITH url → should show URL in log instead of None
print("=== Scenario 3: Short content WITH URL (should show URL in log) ===", file=sys.stderr)
import logging
# Suppress logging to see if the warning still fires with a meaningful URL
logging.getLogger("trafilatura").setLevel(logging.DEBUG)
result3 = trafilatura.extract(
    "<html><body><p>Tiny</p></body></html>",
    url="https://example.com/short-page",
    output_format="markdown",
    include_links=True,
    include_formatting=True,
)
print(f"Result: {result3!r}", file=sys.stderr)
print(f"\nExpected: Scenario 3 should show 'discarding data: https://example.com/short-page'", file=sys.stderr)
print(f"(if trafilatura's min_output_size check causes discard)", file=sys.stderr)