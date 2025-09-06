# Research: Joplin MCP Server

## Technical Decisions

### Configuration Method (FR-012 Resolution)
**Decision**: Environment variables with optional config file fallback  
**Rationale**: 
- Environment variables are standard for server deployments
- Config file provides development convenience
- Follows 12-factor app principles for configuration
- Compatible with container deployments

**Alternatives considered**:
- CLI arguments only: Too cumbersome for server deployment
- Config file only: Harder to containerize and deploy

### MCP SDK Implementation
**Decision**: Use official Python MCP SDK from Anthropic  
**Rationale**:
- Official implementation ensures protocol compliance
- Built-in server infrastructure and tool registration
- Active maintenance and updates
- Type-safe tool definitions with Pydantic

**Alternatives considered**:
- Custom MCP implementation: Too complex, protocol compliance risk
- MCP-compatible REST API: Doesn't leverage MCP ecosystem

### Joplin API Integration
**Decision**: Joplin Web Clipper API via HTTP  
**Rationale**:
- Well-documented REST API
- Supports both local and remote Joplin instances
- Token-based authentication available
- Comprehensive access to notes, notebooks, and metadata

**Alternatives considered**:
- Direct database access: Breaks encapsulation, version compatibility issues
- Joplin Terminal API: Limited functionality, harder to integrate

### Async HTTP Client
**Decision**: httpx for HTTP client operations  
**Rationale**:
- Full async/await support for concurrent requests
- Excellent compatibility with MCP server async architecture
- Built-in request/response validation
- Timeout and retry mechanisms

**Alternatives considered**:
- requests: Synchronous, would block MCP server
- aiohttp ClientSession: More complex setup, httpx simpler

### Error Handling Strategy
**Decision**: Graceful degradation with structured error responses  
**Rationale**:
- MCP clients need actionable error information
- Partial failures should not crash entire server
- Connection issues are common and recoverable

**Implementation approach**:
- Retry logic for transient failures
- Circuit breaker pattern for persistent failures
- Detailed error context in MCP responses

### Rate Limiting
**Decision**: Client-side rate limiting with configurable limits  
**Rationale**:
- Respects Joplin server constraints
- Prevents overwhelming personal Joplin instances
- Configurable for different deployment scenarios

**Implementation**: Token bucket algorithm with per-tool limits