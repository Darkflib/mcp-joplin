# Joplin MCP Server

MCP server that provides standardized tools for querying and retrieving notes from Joplin personal knowledge manager through its API, enabling AI assistants to access and reference personal notes contextually.

## Features

- **MCP Protocol Compliance**: Standardized interface for AI assistant integration
- **Joplin API Integration**: Direct connection to local or remote Joplin instances
- **Search Capabilities**: Full-text search across notes, titles, and tags
- **Note Retrieval**: Complete note content and metadata access
- **Notebook Navigation**: Hierarchical notebook structure exploration
- **Rate Limiting**: Respects Joplin API constraints
- **Error Handling**: Graceful degradation during connection failures

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
```

Or create a `.env` file in the project root.

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