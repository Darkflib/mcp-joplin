#!/bin/bash
"""
Installation script for Joplin MCP Server
"""

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python 3.11+ is available
check_python() {
    log_info "Checking Python version..."

    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3.12 &> /dev/null; then
        PYTHON_CMD="python3.12"
    elif command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
        if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l 2>/dev/null || echo "0") == "1" ]]; then
            PYTHON_CMD="python3"
        else
            log_error "Python 3.11 or higher is required. Found: $PYTHON_VERSION"
            exit 1
        fi
    else
        log_error "Python 3.11 or higher is required but not found."
        exit 1
    fi

    log_success "Found Python: $PYTHON_CMD ($(${PYTHON_CMD} --version))"
}

# Check if uv is available, install if not
setup_uv() {
    if command -v uv &> /dev/null; then
        log_success "uv is already installed: $(uv --version)"
        return
    fi

    log_info "Installing uv package manager..."

    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &> /dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        log_error "Neither curl nor wget found. Please install uv manually: https://github.com/astral-sh/uv"
        exit 1
    fi

    # Source the environment to make uv available
    source ~/.bashrc 2>/dev/null || source ~/.zshrc 2>/dev/null || true

    if ! command -v uv &> /dev/null; then
        log_error "Failed to install uv. Please install manually and retry."
        exit 1
    fi

    log_success "uv installed successfully: $(uv --version)"
}

# Create virtual environment
create_venv() {
    log_info "Creating virtual environment..."

    if [[ ! -d ".venv" ]]; then
        uv venv --python "$PYTHON_CMD"
        log_success "Virtual environment created"
    else
        log_info "Virtual environment already exists"
    fi
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."

    # Activate virtual environment
    source .venv/bin/activate

    # Install the package in development mode with all dependencies
    uv pip install -e ".[dev,test]"

    log_success "Dependencies installed successfully"
}

# Setup pre-commit hooks
setup_pre_commit() {
    log_info "Setting up pre-commit hooks..."

    source .venv/bin/activate

    if [[ -f ".pre-commit-config.yaml" ]]; then
        pre-commit install
        log_success "Pre-commit hooks installed"
    else
        log_warning "No .pre-commit-config.yaml found, skipping pre-commit setup"
    fi
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."

    source .venv/bin/activate

    # Check if CLI is available
    if command -v joplin-mcp-server &> /dev/null; then
        log_success "CLI installed successfully"
        joplin-mcp-server --version
    else
        log_error "CLI installation failed"
        exit 1
    fi

    # Run basic tests
    log_info "Running basic tests..."
    if pytest tests/ -v --tb=short; then
        log_success "Basic tests passed"
    else
        log_warning "Some tests failed, but installation completed"
    fi
}

# Create sample configuration
create_sample_config() {
    log_info "Creating sample configuration..."

    if [[ ! -f "config.example.json" ]]; then
        cat > config.example.json << 'EOF'
{
    "joplin": {
        "base_url": "http://localhost:41184",
        "api_token": "your_joplin_api_token_here",
        "timeout": 30.0,
        "max_retries": 3,
        "retry_delay": 1.0
    },
    "rate_limiting": {
        "requests_per_second": 10,
        "burst_size": 20
    },
    "logging": {
        "level": "INFO",
        "format": "json"
    }
}
EOF
        log_success "Sample configuration created: config.example.json"
    else
        log_info "Sample configuration already exists"
    fi
}

# Print usage instructions
print_usage() {
    cat << 'EOF'

🎉 Installation completed successfully!

Next steps:
1. Copy the sample configuration:
   cp config.example.json config.json

2. Edit config.json with your Joplin settings:
   - Set your Joplin API token
   - Adjust base URL if needed (default: http://localhost:41184)

3. Start the MCP server:
   source .venv/bin/activate
   joplin-mcp-server --config config.json

4. For development, run tests:
   source .venv/bin/activate
   pytest

For more information, see the README.md file.

EOF
}

# Main installation function
main() {
    log_info "Starting Joplin MCP Server installation..."

    # Check if we're in the right directory
    if [[ ! -f "pyproject.toml" ]] || ! grep -q "joplin-mcp-server" pyproject.toml; then
        log_error "This script must be run from the joplin-mcp-server root directory"
        exit 1
    fi

    check_python
    setup_uv
    create_venv
    install_dependencies
    setup_pre_commit
    create_sample_config
    verify_installation
    print_usage

    log_success "Installation completed successfully!"
}

# Handle script interruption
trap 'log_error "Installation interrupted"; exit 1' INT TERM

# Run main function
main "$@"
