# Quickstart: Joplin MCP Server

## Integration Test Scenarios

### Scenario 1: Basic Connection and Authentication
**Test**: Verify MCP server can connect to Joplin instance

**Prerequisites**:
- Joplin desktop app running with Web Clipper enabled
- API token configured in Joplin settings
- MCP server configured with correct base URL and token

**Steps**:
1. Start Joplin MCP server with configuration
2. MCP client connects to server
3. Server attempts authentication with Joplin API
4. Verify connection established successfully

**Expected Result**: 
- Server reports "Connected" status
- Health check ping succeeds
- No authentication errors in logs

**Failure Modes**:
- Joplin not running: Connection refused error
- Invalid token: HTTP 401 authentication error
- Wrong URL: Connection timeout or 404 error

### Scenario 2: Search Notes Functionality
**Test**: Search for notes containing specific keywords

**Prerequisites**:
- Connected MCP server (from Scenario 1)
- At least 5 notes in Joplin with varied content
- Notes containing search terms "project", "meeting", "todo"

**Steps**:
1. MCP client calls `search_notes` tool with query="project"
2. Server queries Joplin API with search parameters
3. Joplin returns matching notes
4. Server formats results as MCP response

**Expected Result**:
- Returns list of notes containing "project" in title or body
- Results include note ID, title, content snippet
- Relevance scores assigned (0.0-1.0 range)
- Total count matches actual results

**Failure Modes**:
- No results: Empty results array but no error
- Large result set: Proper pagination applied
- Invalid query: Validation error returned

### Scenario 3: Retrieve Full Note Content
**Test**: Get complete note details by ID

**Prerequisites**:
- Connected MCP server
- Valid note ID from previous search results

**Steps**:
1. MCP client calls `get_note` tool with specific note_id
2. Server requests full note details from Joplin API
3. Server returns complete note content and metadata

**Expected Result**:
- Full markdown content of note returned
- All metadata fields populated (creation time, update time, tags)
- Notebook association included
- Content properly formatted

**Failure Modes**:
- Invalid note ID: HTTP 404 error, descriptive message
- Large note content: Proper handling without timeout
- Corrupted note: Error handling with context

### Scenario 4: List Notebooks Hierarchy
**Test**: Retrieve notebook structure and organization

**Prerequisites**:
- Connected MCP server
- Multiple notebooks including nested structure
- At least one root notebook and one sub-notebook

**Steps**:
1. MCP client calls `list_notebooks` tool with recursive=true
2. Server queries Joplin API for all notebooks
3. Server builds hierarchical structure
4. Returns nested notebook tree

**Expected Result**:
- All notebooks returned with parent-child relationships
- Root notebooks have null parent_id
- Sub-notebooks properly nested under parents
- Notebook metadata included (creation times, update times)

**Failure Modes**:
- Circular references: Detection and graceful handling
- Large notebook tree: Efficient recursive processing
- Empty notebooks: Proper handling of notebooks with no notes

### Scenario 5: Error Handling and Recovery
**Test**: Server behavior during connection failures and errors

**Prerequisites**:
- Initially connected MCP server

**Steps**:
1. Simulate Joplin shutdown (close application)
2. MCP client attempts to search notes
3. Server detects connection failure
4. Restart Joplin
5. Server attempts reconnection
6. Verify functionality restored

**Expected Result**:
- Connection failure detected and logged
- Graceful error response to MCP client (not crash)
- Automatic reconnection when Joplin available
- Service resumed without manual intervention

**Failure Modes**:
- Server crash: Should never happen, always return errors
- Hanging connections: Timeout handling prevents indefinite waits
- Partial failures: Individual tool failures don't affect others

### Scenario 6: Rate Limiting and Performance
**Test**: Server handles high request volume appropriately

**Prerequisites**:
- Connected MCP server with rate limiting enabled
- Large Joplin database (100+ notes, 10+ notebooks)

**Steps**:
1. MCP client makes rapid sequential search requests
2. Server applies rate limiting logic
3. Measure response times and throughput
4. Verify no requests dropped or failed

**Expected Result**:
- Consistent response times under <500ms
- Rate limiting prevents Joplin API overload
- All requests processed or gracefully queued
- Server remains stable under load

**Failure Modes**:
- Rate limit exceeded: HTTP 429 responses with retry-after
- Memory exhaustion: Request queuing with backpressure
- Slow responses: Timeout handling and circuit breaker activation

## Manual Validation Steps

1. **Setup Verification**: 
   - Start Joplin, enable Web Clipper, note API token
   - Configure MCP server with environment variables
   - Verify server startup logs show successful configuration

2. **Basic Functionality**:
   - Test each MCP tool individually with various parameters
   - Verify responses match expected schemas
   - Check error handling with invalid inputs

3. **Integration Testing**:
   - Use MCP client (Claude, etc.) to interact with server
   - Perform realistic knowledge queries and note retrieval
   - Validate contextual responses include actual note content

4. **Edge Case Testing**:
   - Very large notes (>100KB content)
   - Special characters in search queries
   - Unicode content handling
   - Network interruption recovery