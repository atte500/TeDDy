# Component Design: MarkdownPlanBuilder
- **Status:** Implemented
- **Source:** [`tests/harness/drivers/plan_builder.py`](/tests/harness/drivers/plan_builder.py)

## Purpose
A fluent test-harness driver that builds valid Markdown plan strings for acceptance tests. It abstracts the plan protocol's headers, rationale block, and action fencing so tests express intent rather than raw Markdown.

## Consumers
- Acceptance test suites: Build plan content for the `--plan-content` bypass and the [`CliTestAdapter`](./cli_adapter.md).

## Dependencies
None — the builder uses only the Python standard library.

## Class Invariants
- `fluent_chain`: Every mutator returns `self` to allow chaining.
- `root_relative_links`: `_path_link` renders a path as a root-relative Markdown link unless it is already a link.
- `protocol_valid_defaults`: `build` always emits the H1 title, the status and plan-type metadata, a rationale block, and either a `## Message` section or a `## Action Plan`.
- `fence_nesting`: Action content is wrapped in a four-backtick fence; `EDIT` uses a five-backtick fence for its `#### FIND:` and `#### REPLACE:` sub-blocks.

## Inbound Ports
None — this is a test harness component.

## Outbound Ports
None — this is a test harness component.

## Data Contracts
- **`build` return:** A single Markdown plan `str` conforming to the plan protocol.
- **Action record:** An internal dict carrying `type`, `params`, and `content_blocks`.

## Operations

### `MarkdownPlanBuilder(title)`
- **Postconditions:** Initializes the builder with the plan title, the default agent (`Developer`), and no actions.

### `with_agent(agent) -> MarkdownPlanBuilder`
- **Postconditions:** Sets the `- **Agent:**` header value; `None` omits the header.

### `with_rationale(rationale) -> MarkdownPlanBuilder`
- **Postconditions:** Sets a custom rationale block.

### `with_message(content) -> MarkdownPlanBuilder`
- **Postconditions:** Switches the plan to a `## Message` section instead of a `## Action Plan`.

### `add_action(action_type, params, content_blocks=None)`
- **Postconditions:** Appends a generic action record for later rendering.

### `add_create(path, content, overwrite=False, description="Creating file")`
- **Postconditions:** Appends a `CREATE` action carrying the linked path and the content block; `overwrite` adds an `Overwrite` key.

### `add_read(resource, description="Reading resource", key="Resource")`
- **Postconditions:** Appends a `READ` action with the linked resource under the given key.

### `add_edit(path, find_replace, replace=None, description="Editing file", match_all=False)`
- **Postconditions:** Appends an `EDIT` action. A list argument emits one `FIND:`/`REPLACE:` pair per entry; `match_all` adds a `Match All` key.

### `add_execute(command, description="Running command", **kwargs)`
- **Postconditions:** Appends an `EXECUTE` action carrying the command, the expected outcome, and any of `allow_failure`, `background`, `timeout`, `cwd`, or `env` passed as keyword arguments.

### `add_research(queries, description="Searching web")`
- **Postconditions:** Appends a `RESEARCH` action with the queries joined into one code block.

### `build() -> str`
- **Postconditions:** Renders the accumulated header, rationale, and actions into a valid Markdown plan string.

### Internal helpers
`_path_link` renders root-relative links. `_render_params` renders the bulleted metadata list. `_render_content_blocks` renders the fenced blocks. `_build_action` assembles one action.
