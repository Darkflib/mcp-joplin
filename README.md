# Joplin Remote MCP server for LLM integration

This project provides a Streamable HTTP MCP server over the Joplin Data API (Web Clipper).
It enables MCP clients (including coding agents/LLMs) to read and manage notes, folders,
tags, search, and attachments.

## Features

- Remote Joplin access via MCP Streamable HTTP
- API-key protected MCP endpoint (`X-API-Key`)
- Notes CRUD
- Folder (notebook) list/tree/create/update/delete
- Tag list/create/delete + attach/remove tag on note
- Search across Joplin items
- Attachment/resource support:
   - list/get/create/delete resources
   - list note resources
   - attach/detach resource links in note bodies

## Protocol support

Built on the MCP Python SDK 2.x. One endpoint serves both:

- **MCP 2026-07-28** clients: stateless single-exchange requests (no `initialize`, no session id).
- **Earlier protocol versions** (handshake-based, e.g. 2025-11-25): served statelessly with JSON responses.

Clients must address the server as `127.0.0.1`, `localhost` or `[::1]` with an explicit port;
the SDK's DNS rebinding protection rejects any other `Host` header, or one without a port, with `421`.

## Runtime endpoints

- MCP endpoint: `http://$MCP_HOST:$MCP_PORT/mcp`
- `GET /health`: **readiness**. `200` only when Joplin's Web Clipper service is reachable *and*
  accepts `JOPLIN_TOKEN`; otherwise `503` with `{"ok": false, "joplin": "unreachable" |
  "unauthorized" | "error", "detail": ...}`. The probe result is cached for 15 s, and concurrent
  requests share a single probe, so polling it is cheap. Every state change is logged with its reason.
- `GET /health/live`: **liveness**. Always `200` while the process is serving.

Both health endpoints are unauthenticated and return no secrets or note data.

All MCP requests must include:

- `X-API-Key: $MCP_API_KEY`

## Exposed MCP resources

- `joplin-note://{note_id}`
- `joplin-folders://tree{?root_id}` (plain `joplin-folders://tree` for the whole tree; `?root_id=<folder id>` for a subtree)

## Exposed MCP tools

Every tool carries MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`), so
clients can auto-approve reads and ask before destructive calls.

- Notes:
   - `notes_get`
   - `notes_list`
   - `notes_create`
   - `notes_append`: add text to the end of a note without touching the rest
   - `notes_replace_text`: replace exact text; refused unless it matches exactly
     `expected_count` times (default 1)
   - `notes_update`: rename, move, or replace the *whole* body
   - `notes_delete`

`notes_update`, `notes_append` and `notes_replace_text` accept an optional
`expected_updated_time` (from your last read). If the note changed since then, the edit is
refused instead of overwriting the other change.
- Folders:
   - `folders_list`
   - `folders_tree`
   - `folders_create`
   - `folders_update`
   - `folders_delete`
- Tags:
   - `tags_list`
   - `tags_create`
   - `tags_delete`
   - `tags_add_note`
   - `tags_remove_note`
- Resources (attachments):
   - `resources_list`
   - `resources_get`
   - `resources_get_content`
   - `resources_create`
   - `resources_delete`
   - `notes_list_resources`
   - `notes_attach_resource`
   - `notes_detach_resource`
- Search:
   - `search`

## Installation

### Setup (uv)

1. Create a .env from the example:

   - copy .env.example to .env
2. Fill in:

   - JOPLIN_TOKEN
   - MCP_API_KEY (for `serve` only; at least 12 characters, e.g. `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`)
3. Install dependencies:

   - uv sync --all-extras

### Run

```bash
uv run mcp-joplin-streamable-sse            # same as `serve`
uv run mcp-joplin-streamable-sse serve      # Streamable HTTP on $MCP_HOST:$MCP_PORT (needs MCP_API_KEY)
uv run mcp-joplin-streamable-sse stdio      # MCP over stdin/stdout for clients that launch servers
uv run mcp-joplin-streamable-sse doctor     # check config, Joplin reachability/token, and the port
```

Exit codes: `0` ok, `1` runtime failure (or a failed `doctor` check), `2` invalid configuration.
Configuration errors are a one-line message naming the setting, never its value.

### Run under the Joplin sidecar launcher

[joplin-sidecar-launcher](https://github.com/Darkflib/joplin-sidecar-launcher) (0.4+) starts the
server with Joplin, supplies `JOPLIN_BASE_URL`/`JOPLIN_TOKEN` from its own settings, and stores
`MCP_API_KEY` encrypted (key in the OS keychain) rather than in a plaintext `.env`:

```json
{
  "name": "Joplin MCP",
  "command": "/opt/homebrew/bin/uv",
  "args": ["run", "--project", "/Users/you/mcp-joplin-streamable-sse", "mcp-joplin-streamable-sse"],
  "cwd": "/Users/you/mcp-joplin-streamable-sse",
  "healthUrl": "http://127.0.0.1:5005/health",
  "env": { "MCP_HOST": "127.0.0.1", "MCP_PORT": "5005" },
  "secretEnv": ["MCP_API_KEY"],
  "autostart": true
}
```

Then *Secrets → MCP_API_KEY → Generate* and paste the copied key into your MCP client. Use an
absolute `command` path (Joplin started from the Dock doesn't inherit your shell `PATH`).

Because `healthUrl` points at the readiness endpoint, the panel shows **unhealthy** when Joplin's
Web Clipper service is off or the token has been revoked. Expand the log to see why. Point it at
`/health/live` instead if you only want to know that the process is up.

### Connect an MCP client

Streamable HTTP, with the API key as a header. For example, Claude Code:

```bash
claude mcp add --transport http joplin http://127.0.0.1:5005/mcp --header "X-API-Key: <key>"
```

or a client JSON config that supports headers:

```json
{
  "mcpServers": {
    "joplin": {
      "type": "http",
      "url": "http://127.0.0.1:5005/mcp",
      "headers": { "X-API-Key": "<key>" }
    }
  }
}
```

Address the server as `127.0.0.1`, `localhost` or `[::1]` **with an explicit port**. Any other
`Host`, or one without a port, is rejected with `421` (DNS rebinding protection).

For clients that can only launch stdio servers, run `stdio` directly (no sidecar, no API key).
Note that `JOPLIN_TOKEN` then lives in that client's config:

```json
{
  "mcpServers": {
    "joplin": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "--project", "/Users/you/mcp-joplin-streamable-sse", "mcp-joplin-streamable-sse", "stdio"],
      "env": { "JOPLIN_TOKEN": "<joplin web clipper token>" }
    }
  }
}
```

## Development

- Install (with dev extras):
   - `uv sync --all-extras`
- Run tests:
   - `uv run python -m pytest -q`

## References

[Joplin Data API reference](https://joplinapp.org/help/api/references/rest_api/) -- the API documentation for Joplin, which provides details on how to interact with your notes and other data. Note: this is the data API, the plugin API is different and not used here.

In the documentation below, the token may not be specified every time however you will need to include it.

```bash
curl http://localhost:41184/notes?token=ABCD123ABCD123ABCD123ABCD123ABCD123
curl --data '{ "title": "My note", "body": "Some note in **Markdown**"}' http://localhost:41184/notes
curl -X DELETE http://localhost:41184/tags/ABCD1234/notes/EFGH789
```

## Read-only mode

Set `MCP_READ_ONLY=true` to register only the tools that read the notebook (get, list, tree,
search, attachment metadata/content). Tools that create, edit or delete are not offered at all,
so they don't appear in `tools/list`. Resources are unaffected. The default is `false`.

Under the sidecar launcher, add it to the entry's `env`:
`"env": { "MCP_READ_ONLY": "true", ... }`.

## Security

- Do not commit .env
- Use `MCP_READ_ONLY=true` for clients that only need to read
- Rotate JOPLIN_TOKEN if it was ever shared or committed
- Keep MCP bound to 127.0.0.1 unless you have additional network protections
- The Joplin token is redacted from tool errors and logs (Joplin only accepts it as a URL
  query parameter, so request URLs are never logged)
