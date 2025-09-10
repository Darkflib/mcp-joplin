# Joplin MCP Server

MCP server that provides standardized tools for querying and retrieving notes from Joplin personal knowledge manager through its API, enabling AI assistants to access and reference personal notes contextually.

## Features

- **MCP Protocol Compliance**: Standardized interface for AI assistant integration
- **Joplin API Integration**: Direct connection to local or remote Joplin instances
- **Search Capabilities**: Full-text search across notes, titles, and tags
- **Note Retrieval**: Complete note content and metadata access
- **Notebook Navigation**: Hierarchical notebook structure exploration
- **Note Writing**: Create and update notes (when enabled)
- **Rate Limiting**: Respects Joplin API constraints
- **Error Handling**: Graceful degradation during connection failures
- **Security**: Safe by default read-only access with opt-in write operations

## Installation

```bash
# Install from source
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

## Configuration

Configure via environment variables:

```bash
export JOPLIN_API_URL="http://localhost:41184"
export JOPLIN_API_TOKEN="your-api-token-here"
export MCP_SERVER_PORT="3000"

# Optional: Enable write operations (disabled by default for security)
export JOPLIN_ALLOW_WRITE_OPERATIONS="true"
```

Or create a `.env` file in the project root.

### Write Operations

Write operations (creating and updating notes) are **disabled by default** for security. To enable them:

**Option 1: Environment Variable**
```bash
export JOPLIN_ALLOW_WRITE_OPERATIONS="true"
```

**Option 2: Configuration File**
```json
{
  "joplin": {
    "base_url": "http://localhost:41184",
    "api_token": "your-api-token-here",
    "allow_write_operations": true
  }
}
```

When enabled, the following additional MCP tools become available:
- `create_note`: Create new notes with optional content and notebook placement
- `update_note`: Update existing note titles, content, or move between notebooks

## Usage

```bash
# Start the MCP server
joplin-mcp-server --port 3000

# With config file
joplin-mcp-server --config-file config.json
```

## Development

```bash
# Setup development environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run linting
ruff check .
mypy src/
```

## License

MIT