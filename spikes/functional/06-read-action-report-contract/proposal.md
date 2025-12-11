# Spike Proposal: `read` Action Execution Report Contract

This document proposes the structure for the `read` action's output within the final `Execution Report`.

## Guiding Principles
1.  **Clarity:** The report should make it obvious what was read and where it came from.
2.  **Machine & Human Readable:** The output for a successful read should be clean content, suitable for an AI to parse, but wrapped in a way that provides context to a human reviewer.
3.  **Graceful Failures:** Errors should be reported clearly without halting the entire plan execution.

---

## Proposed Contract

### Case 1: Successful Read of a Local File

The content is presented inside a formatted markdown block with the source file path.

**Example Report Snippet:**
````markdown
- **Action:** `read`
- **Status:** `SUCCESS`
- **Source:** `src/main.py`
- **Output:**
  ```python
  # src/main.py
  import typer
  from teddy.main import app

  if __name__ == "__main__":
      app()
  ```
````

---

### Case 2: Successful Read of a Remote URL (with HTML content)

The system will fetch the URL, convert the primary HTML content to Markdown using the `markdownify` library, and present it. This strips away navigation, ads, etc., to provide the core content for the AI.

**Example Report Snippet:**
````markdown
- **Action:** `read`
- **Status:** `SUCCESS`
- **Source:** `https://example.com`
- **Output:**
  ```markdown
  # Example Domain

  This domain is for use in illustrative examples in documents. You may use this domain in literature without prior coordination or asking for permission.

  [More information...](http://www.iana.org/domains/example)
  ```
````

---

### Case 3: Failure - File Not Found

The report explicitly states the failure and the reason.

**Example Report Snippet:**
````markdown
- **Action:** `read`
- **Status:** `FAILURE`
- **Source:** `path/to/nonexistent_file.py`
- **Output:**
  ```
  Error: File not found at path/to/nonexistent_file.py
  ```
````

---

### Case 4: Failure - URL Cannot Be Reached

The report provides the specific HTTP error or connection error.

**Example Report Snippet:**
````markdown
- **Action:** `read`
- **Status:** `FAILURE`
- **Source:** `https://a-nonexistent-domain.dev`
- **Output:**
  ```
  Error: Could not retrieve content from https://a-nonexistent-domain.dev. Reason: Connection Timeout
  ```
````
