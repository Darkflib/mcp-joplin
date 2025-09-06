# Tasks: Joplin MCP Server

**Input**: Design documents from `/Users/mike/miketest/specs/001-remote-mcp-server/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

## Execution Flow (main)
✅ All design documents loaded and analyzed
✅ Tech stack: Python 3.11+, MCP SDK, httpx, pydantic  
✅ Entities: Note, Notebook, SearchResult, Connection, MCPTool
✅ MCP Tools: search_notes, get_note, list_notebooks, get_notes_in_notebook
✅ Integration scenarios: 6 test scenarios identified
✅ Task generation rules applied: TDD, parallel marking, dependencies

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- All paths relative to repository root

## Path Conventions
Single project structure: `src/`, `tests/` at repository root

## Phase 3.1: Setup
- [ ] T001 Create Python project structure with src/ and tests/ directories
- [ ] T002 Initialize Python project with pyproject.toml, dependencies (mcp, httpx, pydantic), and virtual environment
- [ ] T003 [P] Configure pre-commit hooks, ruff linting, and mypy type checking

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests - MCP Tools
- [ ] T004 [P] Contract test search_notes tool in tests/contract/test_search_notes.py
- [ ] T005 [P] Contract test get_note tool in tests/contract/test_get_note.py  
- [ ] T006 [P] Contract test list_notebooks tool in tests/contract/test_list_notebooks.py
- [ ] T007 [P] Contract test get_notes_in_notebook tool in tests/contract/test_get_notes_in_notebook.py

### Integration Tests - Quickstart Scenarios
- [ ] T008 [P] Integration test basic connection and authentication in tests/integration/test_connection.py
- [ ] T009 [P] Integration test search notes functionality in tests/integration/test_search.py
- [ ] T010 [P] Integration test retrieve full note content in tests/integration/test_note_retrieval.py
- [ ] T011 [P] Integration test list notebooks hierarchy in tests/integration/test_notebooks.py
- [ ] T012 [P] Integration test error handling and recovery in tests/integration/test_error_handling.py
- [ ] T013 [P] Integration test rate limiting and performance in tests/integration/test_performance.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Data Models
- [ ] T014 [P] Note model with validation in src/models/note.py
- [ ] T015 [P] Notebook model with validation in src/models/notebook.py
- [ ] T016 [P] SearchResult model with validation in src/models/search_result.py
- [ ] T017 [P] Connection model with validation in src/models/connection.py
- [ ] T018 [P] MCPTool model with validation in src/models/mcp_tool.py

### Core Services
- [ ] T019 Joplin API client service in src/services/joplin_client.py
- [ ] T020 Search service with relevance scoring in src/services/search_service.py
- [ ] T021 Connection manager with retry logic in src/services/connection_manager.py
- [ ] T022 Rate limiting service in src/services/rate_limiter.py

### MCP Tool Implementations
- [ ] T023 [P] search_notes tool handler in src/tools/search_notes.py
- [ ] T024 [P] get_note tool handler in src/tools/get_note.py
- [ ] T025 [P] list_notebooks tool handler in src/tools/list_notebooks.py
- [ ] T026 [P] get_notes_in_notebook tool handler in src/tools/get_notes_in_notebook.py

### Server Infrastructure
- [ ] T027 MCP server setup and tool registration in src/server.py
- [ ] T028 Configuration management (env vars + config file) in src/config.py
- [ ] T029 CLI entry point with server startup in src/cli.py

## Phase 3.4: Integration
- [ ] T030 Wire tool handlers to MCP server in src/server.py
- [ ] T031 Add structured logging with JSON output in src/logging_config.py
- [ ] T032 Error handling middleware for all tools in src/middleware/error_handler.py
- [ ] T033 Health check and connection validation in src/middleware/health_check.py

## Phase 3.5: Polish
- [ ] T034 [P] Unit tests for data models in tests/unit/test_models.py
- [ ] T035 [P] Unit tests for services in tests/unit/test_services.py
- [ ] T036 [P] Performance optimization and caching in src/services/cache.py
- [ ] T037 [P] Package setup.py and installation scripts
- [ ] T038 Run all integration tests from quickstart.md scenarios

## Dependencies
- **Setup Phase**: T001 → T002 → T003 (sequential)
- **Contract Tests**: All T004-T007 can run in parallel (different files)
- **Integration Tests**: All T008-T013 can run in parallel (different files)  
- **Models**: All T014-T018 can run in parallel (different files)
- **Services**: T019 before T020-T022 (T020-T022 depend on JoplinClient)
- **Tools**: All T023-T026 can run in parallel (different files, depend on models/services)
- **Server**: T027-T029 depend on tools and services
- **Integration**: T030-T033 depend on server infrastructure
- **Polish**: T034-T038 can run in parallel after core implementation

## Parallel Execution Examples

### Phase 3.2 - Contract Tests (All Parallel)
```bash
# Launch all contract tests together:
Task: "Contract test search_notes tool in tests/contract/test_search_notes.py"
Task: "Contract test get_note tool in tests/contract/test_get_note.py"  
Task: "Contract test list_notebooks tool in tests/contract/test_list_notebooks.py"
Task: "Contract test get_notes_in_notebook tool in tests/contract/test_get_notes_in_notebook.py"
```

### Phase 3.2 - Integration Tests (All Parallel)
```bash
# Launch all integration tests together:
Task: "Integration test basic connection in tests/integration/test_connection.py"
Task: "Integration test search functionality in tests/integration/test_search.py"
Task: "Integration test note retrieval in tests/integration/test_note_retrieval.py" 
Task: "Integration test notebooks hierarchy in tests/integration/test_notebooks.py"
Task: "Integration test error handling in tests/integration/test_error_handling.py"
Task: "Integration test performance in tests/integration/test_performance.py"
```

### Phase 3.3 - Data Models (All Parallel)
```bash
# Launch all model creation together:
Task: "Note model with validation in src/models/note.py"
Task: "Notebook model with validation in src/models/notebook.py"
Task: "SearchResult model with validation in src/models/search_result.py"
Task: "Connection model with validation in src/models/connection.py"
Task: "MCPTool model with validation in src/models/mcp_tool.py"
```

### Phase 3.3 - MCP Tools (All Parallel After Services)
```bash
# Launch all tool handlers together:
Task: "search_notes tool handler in src/tools/search_notes.py"
Task: "get_note tool handler in src/tools/get_note.py"
Task: "list_notebooks tool handler in src/tools/list_notebooks.py" 
Task: "get_notes_in_notebook tool handler in src/tools/get_notes_in_notebook.py"
```

## Notes
- [P] tasks = different files, no dependencies
- ⚠️ **CRITICAL**: All tests (T004-T013) MUST fail before implementing (T014+)
- Verify tests fail before implementing to ensure RED phase of TDD
- Commit after each task completion
- Focus on constitutional compliance: library-first, CLI interface, structured logging

## Task Generation Rules Applied
✅ Each MCP tool contract → contract test task [P] (T004-T007)
✅ Each integration scenario → integration test [P] (T008-T013)  
✅ Each entity in data-model → model creation task [P] (T014-T018)
✅ Each service identified → service task based on dependencies (T019-T022)
✅ Each MCP tool → implementation task [P] (T023-T026)
✅ Infrastructure and polish tasks based on plan requirements

## Validation Checklist
✅ All MCP tools have corresponding contract tests (T004-T007)
✅ All entities have model tasks (T014-T018)  
✅ All contract tests come before implementation (T004-T013 before T014+)
✅ Parallel tasks truly independent ([P] tasks use different files)
✅ Each task specifies exact file path
✅ No task modifies same file as another [P] task
✅ TDD order strictly enforced (tests must fail first)