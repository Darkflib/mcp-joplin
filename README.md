# mcp-joplin (archived)

This was the first, stdio-only MCP server for [Joplin](https://joplinapp.org/): four read-only
tools on the 2025 MCP SDK. It is no longer maintained.

**Use [Darkflib/mcp-joplin-streamable-sse](https://github.com/Darkflib/mcp-joplin-streamable-sse)
instead.** It supersedes this server:

- MCP SDK 2.x, serving the 2026-07-28 protocol and earlier clients from one endpoint
- Streamable HTTP (API-key protected) and stdio
- Notes, folders, tags, attachments and search, with read-only mode and safer edit tools
- Live note-change notifications, and attachments as native image/audio/text content
- Runs under the [Joplin sidecar launcher](https://github.com/Darkflib/joplin-sidecar-launcher)

## The old code

Nothing was rewritten: the last version of the original server is commit
[`6d34444`](https://github.com/Darkflib/mcp-joplin/tree/6d3444464c172a3844e49ea4cc06701ce2b535f8).

```bash
git clone https://github.com/Darkflib/mcp-joplin.git
cd mcp-joplin
git checkout 6d3444464c172a3844e49ea4cc06701ce2b535f8
```
