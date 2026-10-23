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

Clients must address the server as `127.0.0.1:<port>` (with an explicit port): the SDK's DNS
rebinding protection rejects other `Host` headers with `421`.

## Runtime endpoints

- MCP endpoint: `http://$MCP_HOST:$MCP_PORT/mcp`
- Health endpoint: `GET /health` (intentionally unauthenticated)

All MCP requests must include:

- `X-API-Key: $MCP_API_KEY`

## Exposed MCP resources

- `joplin-note://{note_id}`
- `joplin-folders://tree{?root_id}` (plain `joplin-folders://tree` for the whole tree; `?root_id=<folder id>` for a subtree)

## Exposed MCP tools

- Notes:
   - `notes_get`
   - `notes_list`
   - `notes_create`
   - `notes_update`
   - `notes_delete`
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
   - MCP_API_KEY (at least 12 characters, e.g. `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`)
3. Install dependencies:

   - uv sync --all-extras

### Run

- uv run mcp-joplin-streamable-sse

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

## Security

- Do not commit .env
- Rotate JOPLIN_TOKEN if it was ever shared or committed
- Keep MCP bound to 127.0.0.1 unless you have additional network protections
- The Joplin token is redacted from tool errors and logs (Joplin only accepts it as a URL
  query parameter, so request URLs are never logged)
