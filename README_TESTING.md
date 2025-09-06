# Testing the Joplin MCP Server

This directory contains the Joplin MCP Server and testing utilities.

## Quick Test

To test if the MCP server is working correctly:

### 1. Test Connection Only
```bash
uv run python test_mcp.py --connection-only
```

### 2. Test Full MCP Server
```bash
uv run python test_mcp.py
```

## Running the MCP Server

### Standalone MCP Server
```bash
# Run the MCP server for use with MCP clients
uv run python mcp_server.py --config-file config.json
```

### Original CLI Server
```bash
# Run the original CLI server
uv run joplin-mcp-server --config-file config.json
```

## MCP Client Configuration

To use this server with Claude Desktop or other MCP clients, add this to your MCP configuration:

```json
{
  "mcpServers": {
    "joplin": {
      "command": "uv",
      "args": [
        "run", 
        "python", 
        "/path/to/your/project/mcp_server.py",
        "--config-file",
        "/path/to/your/project/config.json"
      ]
    }
  }
}
```

## Available Tools

The server provides these MCP tools:

1. **search_notes** - Search for notes by content, title, or tags
2. **get_note** - Retrieve a specific note by ID
3. **list_notebooks** - List all notebooks
4. **get_notes_in_notebook** - Get all notes in a specific notebook

## Configuration

Make sure your `config.json` has the correct Joplin API settings:

```json
{
  "joplin": {
    "base_url": "http://localhost:41184",
    "api_token": "your-joplin-api-token"
  }
}
```

## Troubleshooting

- Ensure Joplin is running and the Web Clipper service is enabled
- Check that the API token in config.json is correct
- Verify the base_url matches your Joplin Web Clipper settings