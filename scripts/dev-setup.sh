#!/bin/bash
"""
Development environment setup script for Joplin MCP Server
"""

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Development setup
setup_dev_environment() {
    log_info "Setting up development environment..."
    
    # Install development dependencies
    source .venv/bin/activate
    uv pip install -e ".[dev]"
    
    # Setup pre-commit hooks
    if [[ -f ".pre-commit-config.yaml" ]]; then
        pre-commit install
        pre-commit install --hook-type commit-msg
        log_success "Pre-commit hooks installed"
    fi
    
    # Create development configuration
    if [[ ! -f "config.dev.json" ]]; then
        cat > config.dev.json << 'EOF'
{
    "joplin": {
        "base_url": "http://localhost:41184",
        "api_token": "dev_token_replace_me",
        "timeout": 10.0,
        "max_retries": 1,
        "retry_delay": 0.5
    },
    "rate_limiting": {
        "requests_per_second": 100,
        "burst_size": 200
    },
    "logging": {
        "level": "DEBUG",
        "format": "text"
    }
}
EOF
        log_success "Development configuration created: config.dev.json"
    fi
    
    # Run linting and formatting
    log_info "Running code formatting and linting..."
    ruff check --fix src/ tests/
    black src/ tests/
    isort src/ tests/
    
    log_success "Development environment setup complete"
}

# Run all tests
run_tests() {
    log_info "Running all tests..."
    
    source .venv/bin/activate
    
    # Run different test categories
    pytest tests/unit/ -v --tb=short -m "unit"
    pytest tests/contract/ -v --tb=short -m "contract"  
    pytest tests/integration/ -v --tb=short -m "integration"
    
    log_success "All tests completed"
}

# Generate test coverage report
generate_coverage() {
    log_info "Generating test coverage report..."
    
    source .venv/bin/activate
    
    pytest --cov=src --cov-report=html --cov-report=term-missing
    
    log_success "Coverage report generated in htmlcov/"
}

# Type checking
run_type_check() {
    log_info "Running type checking..."
    
    source .venv/bin/activate
    mypy src/
    
    log_success "Type checking completed"
}

# Build package
build_package() {
    log_info "Building package..."
    
    source .venv/bin/activate
    
    # Clean previous builds
    rm -rf dist/ build/ src/*.egg-info/
    
    # Build package
    python -m build
    
    log_success "Package built in dist/"
}

# Main function
main() {
    case "${1:-setup}" in
        setup)
            setup_dev_environment
            ;;
        test)
            run_tests
            ;;
        coverage)
            generate_coverage
            ;;
        typecheck)
            run_type_check
            ;;
        build)
            build_package
            ;;
        all)
            setup_dev_environment
            run_type_check
            run_tests
            generate_coverage
            build_package
            ;;
        *)
            echo "Usage: $0 {setup|test|coverage|typecheck|build|all}"
            echo "  setup    - Setup development environment"
            echo "  test     - Run all tests"
            echo "  coverage - Generate test coverage report"
            echo "  typecheck - Run type checking"
            echo "  build    - Build package"
            echo "  all      - Run all of the above"
            exit 1
            ;;
    esac
}

main "$@"