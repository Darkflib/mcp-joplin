# Makefile for Joplin MCP Server

.PHONY: help install dev-install test test-unit test-contract test-integration coverage lint format typecheck build clean run docs serve

# Default target
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation targets
install: ## Install the package for production use
	./install.sh

dev-install: ## Install the package for development
	./scripts/dev-setup.sh setup

# Testing targets
test: ## Run all tests
	source .venv/bin/activate && pytest

test-unit: ## Run unit tests only
	source .venv/bin/activate && pytest tests/unit/ -v -m "unit"

test-contract: ## Run contract tests only
	source .venv/bin/activate && pytest tests/contract/ -v -m "contract"

test-integration: ## Run integration tests only
	source .venv/bin/activate && pytest tests/integration/ -v -m "integration"

test-quick: ## Run tests without coverage
	source .venv/bin/activate && pytest --no-cov -x -v

coverage: ## Generate test coverage report
	source .venv/bin/activate && pytest --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/"

# Code quality targets
lint: ## Run linter (ruff)
	source .venv/bin/activate && ruff check src/ tests/

lint-fix: ## Fix linting issues automatically
	source .venv/bin/activate && ruff check --fix src/ tests/

format: ## Format code with black and isort
	source .venv/bin/activate && black src/ tests/
	source .venv/bin/activate && isort src/ tests/

typecheck: ## Run type checking with mypy
	source .venv/bin/activate && mypy src/

# Quality assurance - run all checks
qa: lint typecheck test ## Run all quality assurance checks

# Build targets
build: ## Build the package
	source .venv/bin/activate && python -m build

clean: ## Clean build artifacts
	rm -rf dist/ build/ src/*.egg-info/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

# Development targets
run: ## Run the MCP server (requires config.json)
	source .venv/bin/activate && joplin-mcp-server --config config.json

run-dev: ## Run the MCP server with development config
	source .venv/bin/activate && joplin-mcp-server --config config.dev.json --log-level DEBUG

# Docker targets (if needed later)
docker-build: ## Build Docker image
	docker build -t joplin-mcp-server .

docker-run: ## Run Docker container
	docker run -p 8000:8000 --env-file .env joplin-mcp-server

# Documentation targets
docs: ## Generate documentation
	@echo "Documentation generation not yet implemented"

serve: ## Serve documentation locally
	@echo "Documentation serving not yet implemented"

# Pre-commit hooks
pre-commit: ## Run pre-commit hooks on all files
	source .venv/bin/activate && pre-commit run --all-files

# Performance and profiling
benchmark: ## Run performance benchmarks
	source .venv/bin/activate && python -m pytest tests/integration/test_performance.py -v --benchmark-only

# Maintenance targets
update-deps: ## Update dependencies
	source .venv/bin/activate && uv pip install --upgrade -e ".[dev,test]"

check-deps: ## Check for security vulnerabilities in dependencies
	source .venv/bin/activate && safety check

# Release targets
check-release: ## Check if ready for release
	@echo "Checking release readiness..."
	@make lint
	@make typecheck
	@make test
	@make build
	@echo "✅ Ready for release"

release-patch: ## Create a patch release
	@echo "Creating patch release..."
	@echo "This would bump version and create release (not implemented)"

release-minor: ## Create a minor release
	@echo "Creating minor release..."
	@echo "This would bump version and create release (not implemented)"

release-major: ## Create a major release
	@echo "Creating major release..."
	@echo "This would bump version and create release (not implemented)"
