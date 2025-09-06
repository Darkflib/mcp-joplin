# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a **Spec-Driven Development** framework that enforces a structured approach to feature development through templates, scripts, and constitutional principles. The workflow follows a strict lifecycle: Specification → Planning → Task Breakdown → Implementation → Validation.

### Core Principles
- **Library-First Architecture**: Every feature starts as a standalone library with CLI interface
- **Test-First Development**: Red-Green-Refactor cycle strictly enforced (tests must fail before implementation)
- **Constitutional Compliance**: All development must adhere to principles in `/memory/constitution.md`
- **Structured Documentation**: All features require complete documentation artifacts before coding

### Directory Structure
```
├── .claude/commands/          # Claude Code slash commands (/specify, /plan, /tasks)
├── memory/                    # Constitutional principles and governance
├── scripts/                   # Automation scripts for feature lifecycle
├── templates/                 # Document templates for specs, plans, tasks
└── specs/[###-feature-name]/  # Generated per-feature documentation
    ├── spec.md               # Feature specification (business requirements)
    ├── plan.md               # Implementation plan (technical design)
    ├── tasks.md              # Executable task breakdown
    ├── research.md           # Technical decisions and alternatives
    ├── data-model.md         # Entity definitions and relationships
    ├── quickstart.md         # Integration test scenarios
    └── contracts/            # API contracts and schemas
```

## Essential Commands

### Development Lifecycle
The framework provides three main slash commands that must be executed in sequence:

1. **`/specify "feature description"`** - Creates feature specification and branch
   - Runs: `scripts/create-new-feature.sh --json "description"`
   - Creates: numbered branch (e.g., `001-user-auth`), spec.md from template
   - Output: Feature branch ready for planning phase

2. **`/plan "implementation details"`** - Creates technical implementation plan
   - Runs: `scripts/setup-plan.sh --json`, loads constitution
   - Creates: research.md, data-model.md, contracts/, quickstart.md, plan.md
   - Output: Complete technical design ready for task breakdown

3. **`/tasks "context"`** - Breaks plan into executable tasks
   - Runs: `scripts/check-task-prerequisites.sh --json`
   - Creates: tasks.md with numbered, ordered, parallelizable tasks
   - Output: Ready-to-execute task list following TDD principles

### Validation Scripts
- `scripts/check-task-prerequisites.sh` - Validates feature branch and documents
- `scripts/common.sh` - Shared utilities for path resolution and validation
- `scripts/update-agent-context.sh` - Updates AI assistant context files

### Key Patterns
- **Feature Branches**: Named `###-feature-name` (e.g., `001-user-registration`)
- **Parallel Tasks**: Marked with `[P]` in tasks.md for concurrent execution
- **Test-First**: Contract tests → Integration tests → Implementation → Unit tests
- **Constitutional Gates**: Each phase validates against `/memory/constitution.md`

## Development Workflow

1. **Start Feature**: Use `/specify` to create specification and branch
2. **Technical Design**: Use `/plan` to create implementation architecture
3. **Task Breakdown**: Use `/tasks` to generate executable implementation plan
4. **Implementation**: Execute tasks.md following TDD (tests first, then implementation)
5. **Validation**: Run constitution compliance checks and performance validation

### Important Notes
- NEVER skip the specification phase - all features must start with `/specify`
- Tests MUST be written and MUST FAIL before any implementation
- Each phase has constitutional compliance gates that must pass
- All paths in scripts must be absolute for proper execution
- Templates are self-contained and executable with built-in validation