# AGENTS.md

Guidance for coding agents working on this repository.

## Project summary

- Python package: `mcp_joplin_streamable_sse`
- Purpose: Streamable HTTP MCP server for Joplin Data API
- Entry point: `uv run mcp-joplin-streamable-sse`
- Python target: 3.12+

## Key files

- `src/mcp_joplin_streamable_sse/asgi.py` - ASGI app, API-key middleware, routing
- `src/mcp_joplin_streamable_sse/mcp_server.py` - MCP resources/tools registration
- `src/mcp_joplin_streamable_sse/joplin_client.py` - async Joplin API client (JSON/bytes/multipart)
- `src/mcp_joplin_streamable_sse/models.py` - response/data models
- `src/mcp_joplin_streamable_sse/settings.py` - environment config
- `src/mcp_joplin_streamable_sse/__main__.py` - CLI (`serve`/`stdio`/`doctor`)
- `src/mcp_joplin_streamable_sse/health.py` - cached Joplin readiness probe
- `src/mcp_joplin_streamable_sse/resource_links.py` - remove resource references from note bodies
- `src/mcp_joplin_streamable_sse/redaction.py` - token redaction for errors and logs

## Exposed MCP surface (current)

### Resources

- `joplin-note://{note_id}`
- `joplin-folders://tree{?root_id}` (plain `joplin-folders://tree` for the whole tree; `?root_id=<folder id>` for a subtree)

### Tools

- Notes: `notes_get`, `notes_list`, `notes_create`, `notes_update`, `notes_delete`
- Folders: `folders_list`, `folders_tree`, `folders_create`, `folders_update`, `folders_delete`
- Tags: `tags_list`, `tags_create`, `tags_delete`, `tags_add_note`, `tags_remove_note`
- Resources: `resources_list`, `resources_get`, `resources_get_content`, `resources_create`, `resources_delete`, `notes_list_resources`, `notes_attach_resource`, `notes_detach_resource`
- Search: `search`

## Environment variables

Required:

- `JOPLIN_TOKEN`
- `MCP_API_KEY` for `serve` only (absent is allowed for `stdio`/`doctor`; at least 12 characters; e.g. `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`)

Optional/defaulted:

- `JOPLIN_BASE_URL` (default `http://127.0.0.1:41184`)
- `MCP_HOST` (default `127.0.0.1`)
- `MCP_PORT` (default `5005`)
- `HTTP_TIMEOUT_SECONDS` (default `15.0`)

## Local dev workflow

1. `uv sync --all-extras`
2. `uv run python -m pytest -q`
3. Run server: `uv run mcp-joplin-streamable-sse`

## Editing guidelines

- Keep changes small and focused.
- Preserve strict typing and existing style.
- Add/adjust tests when behavior changes.
- Keep README and this file in sync with exposed tools/resources.
- Do not commit secrets (`.env` is ignored).

## Behavior notes

- `/health` (readiness: Joplin reachable + token accepted, cached 15 s, 503 otherwise) and
  `/health/live` (liveness) are unauthenticated by design and must never return secrets or note
  data. The sidecar launcher polls `/health` with a 2 s timeout and shows only the status code,
  so the reason for a state change is logged (`health.py`).
- CLI: `serve` (default), `stdio`, `doctor`; exit code 2 = configuration error.
- Collections that a tool needs in full (e.g. the folder tree) go through
  `JoplinClient.get_all`, which follows `has_more` and raises `CollectionTooLargeError`
  past 10,000 items instead of truncating. Never fetch a single page and assume it is everything.
- `notes_detach_resource` edits note bodies via `resource_links.remove_resource_links`: it
  removes only the link/embed constructs (keeping surrounding prose, indentation and hard line
  breaks) and does not write the note when nothing matched. Keep `notes_attach_resource`'s
  label escaping in step with what that module can match.
- MCP endpoint requires `X-API-Key`.
- Attachment content is exchanged as base64 in MCP tools.
- MCP Python SDK 2.x (`mcp.server.mcpserver.MCPServer`); serves the 2026-07-28 protocol and
  earlier handshake-based versions from the same endpoint. Tests cover both via
  `Client(..., mode="legacy" | "2026-07-28")`.
- Joplin failures raise `JoplinApiError`/`JoplinConnectionError` (subclasses of the SDK's
  `ResourceError`) so their message reaches the client; any other exception is reported only as
  "Error executing tool". Never put the request URL in an error or log line: it carries the token.
