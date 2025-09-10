# Joplin MCP Server

MCP server that provides standardized tools for querying and retrieving notes from Joplin personal knowledge manager through its API, enabling AI assistants to access and reference personal notes contextually.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap, Build, and Test the Repository:
1. **Install uv package manager**: `pip install uv` (takes ~5-15 seconds)
2. **Create virtual environment**: `uv venv --python python3.12` (takes ~1 second)  
3. **Activate environment**: `source .venv/bin/activate`
4. **Install dependencies**: `uv pip install -e ".[dev,test]"` (takes ~6-10 seconds)
5. **Test CLI installation**: `joplin-mcp-server --version` 
6. **Run linting**: `ruff check src/ tests/` (takes ~0.02 seconds - expect some linting errors in current codebase)
7. **Run type checking**: `mypy src/` (takes ~9-10 seconds - expect ~90 type errors in current codebase)

### Testing:
- **NEVER CANCEL**: Some tests may have import errors due to missing class definitions. This is expected in the current codebase state.
- **Unit tests**: `pytest tests/unit/ --no-cov -x -v` (fails with import errors - expected)
- **Contract tests**: `pytest tests/contract/ --no-cov -x -v` (takes ~1 second, some tests pass)
- **Quick test without coverage**: `pytest tests/ --no-cov -x -v` (fails with import errors)
- **Test categories available**: unit, contract, integration (use `-m` flag to select)

### Run the Application:
- **Test server startup**: `joplin-mcp-server --config config.example.json --log-level DEBUG`
- **Expected behavior**: Server will start but fail to connect to Joplin (no instance running)
- **Success indicators**: Server logs initialization messages, then fails with "All connection attempts failed"
- The server requires a running Joplin instance on `localhost:41184` with valid API token

### Development Commands:
- **Lint code**: `ruff check src/ tests/`
- **Fix linting issues**: `ruff check --fix src/ tests/`
- **Format code**: `black src/ tests/` and `isort src/ tests/`
- **Type checking**: `mypy src/`
- **Build package**: Install `uv pip install build` then `python -m build` (takes ~25+ seconds, may fail due to network timeouts)

## Validation

### Manual Validation Steps:
- **ALWAYS validate CLI functionality** by running `joplin-mcp-server --help` after making changes
- **Test server startup** with `timeout 10s joplin-mcp-server --config config.example.json --log-level DEBUG`
- **Expected output**: JSON-formatted logs showing server initialization, then connection failures (normal without Joplin running)
- **Validation scenario**: Server should log "Joplin MCP server initialized" and show tools registration messages

### Build Validation:
- **NEVER CANCEL**: Build commands can take 25-45 seconds and may timeout due to network issues
- **Building always requires network access** to PyPI - expect timeouts in restricted environments
- The codebase has known linting errors (~7 ruff errors) and type errors (~90 mypy errors)

## Common Tasks

### Repository Structure:
```
├── src/                    # Main source code
│   ├── cli.py             # Command-line interface entry point  
│   ├── server.py          # MCP server setup and tool registration
│   ├── config.py          # Configuration management
│   ├── models/            # Pydantic data models
│   ├── services/          # Core services (Joplin client, rate limiter)
│   ├── tools/             # MCP tool implementations
│   └── middleware/        # Health check and error handling
├── tests/                 # Test suite organized by type
│   ├── unit/              # Unit tests (have import issues)
│   ├── contract/          # Contract tests (partially working)
│   └── integration/       # Integration tests
├── scripts/               # Development automation scripts
├── Makefile              # Build targets (source command doesn't work in sh)
├── pyproject.toml        # Python project configuration
├── config.example.json   # Sample configuration file
└── install.sh            # Installation script (fails due to network restrictions)
```

### Key Files to Monitor:
- **src/server.py**: Main server registration and tool setup
- **src/cli.py**: Command-line interface and server startup
- **src/services/joplin_client.py**: Joplin API integration
- **pyproject.toml**: Project dependencies and configuration
- **config.example.json**: Sample configuration with connection settings

### Common File Locations:
```bash
# Main entry point
src/cli.py

# Server implementation  
src/server.py

# Configuration
config.example.json
src/config.py

# Test files
tests/unit/
tests/contract/
tests/integration/

# Development scripts
scripts/dev-setup.sh
install.sh
```

### Project Dependencies:
- **Python**: 3.11+ required
- **Package manager**: uv (faster than pip)
- **Key packages**: mcp, httpx, pydantic, click, rich
- **Dev tools**: pytest, ruff, mypy, black, isort
- **Testing**: pytest with asyncio support, respx for HTTP mocking

## Known Issues and Workarounds:
- **Makefile targets fail**: The `source .venv/bin/activate` command doesn't work in sh shell - use bash directly
- **Network timeouts**: Installing/building may fail in restricted environments - use existing installed dependencies
- **Import errors in tests**: Some unit tests fail due to missing class definitions - this is expected
- **Type errors**: ~90 mypy errors exist in current codebase - focus on functionality over type safety
- **Linting errors**: ~7 ruff errors exist - use `ruff check --fix` to auto-fix some issues
- **Install script fails**: Network restrictions prevent downloading uv - use `pip install uv` instead

## Environment Setup:
```bash
# Quick setup for development
pip install uv
uv venv --python python3.12
source .venv/bin/activate  
uv pip install -e ".[dev,test]"
joplin-mcp-server --version

# Test basic functionality
joplin-mcp-server --help
timeout 10s joplin-mcp-server --config config.example.json --log-level DEBUG
```

The codebase is a work-in-progress Python MCP server with some test failures and type issues that are expected. Focus on core functionality and CLI behavior when validating changes.