# Data Model: Joplin MCP Server

## Core Entities

### Note
**Purpose**: Represents an individual Joplin note with all metadata and content

**Fields**:
- `id`: Unique identifier (Joplin note ID)
- `title`: Note title/name
- `body`: Full markdown content
- `parent_id`: Notebook ID containing this note
- `created_time`: Creation timestamp (Unix milliseconds)
- `updated_time`: Last modification timestamp (Unix milliseconds)
- `is_conflict`: Boolean indicating sync conflicts
- `markup_language`: Content format (1=Markdown, 2=HTML)
- `tags`: List of tag names associated with note

**Validation Rules**:
- ID must be valid Joplin note ID format
- Title required (can be empty string)
- Body content validated as UTF-8
- Timestamps must be positive integers
- Parent ID must reference valid notebook

**State Transitions**:
- Created → Updated (on content changes)
- Normal → Conflict (on sync issues)
- Conflict → Resolved (conflict resolution)

### Notebook
**Purpose**: Container for organizing notes with hierarchical structure

**Fields**:
- `id`: Unique identifier (Joplin notebook ID)
- `title`: Notebook display name
- `parent_id`: Parent notebook ID (null for root notebooks)
- `created_time`: Creation timestamp (Unix milliseconds) 
- `updated_time`: Last modification timestamp (Unix milliseconds)

**Validation Rules**:
- ID must be valid Joplin notebook ID format
- Title required and non-empty
- Parent ID must reference existing notebook or be null
- Timestamps must be positive integers
- Circular parent references forbidden

**Relationships**:
- Parent-child hierarchy through parent_id
- One-to-many with Notes

### SearchResult
**Purpose**: Represents search query results with relevance scoring

**Fields**:
- `note_id`: Reference to matching note
- `title`: Note title for display
- `snippet`: Content excerpt showing match context
- `score`: Relevance score (0.0-1.0)
- `match_type`: Where match occurred (title, body, tags)

**Validation Rules**:
- Note ID must reference existing note
- Score between 0.0 and 1.0 inclusive
- Snippet limited to 200 characters
- Match type from enum: title, body, tags, mixed

### Connection
**Purpose**: Manages authentication state and API configuration

**Fields**:
- `base_url`: Joplin API endpoint URL
- `api_token`: Authentication token
- `timeout`: Request timeout in seconds
- `rate_limit`: Maximum requests per minute
- `is_connected`: Current connection status

**Validation Rules**:
- Base URL must be valid HTTP/HTTPS URL
- API token required for authentication
- Timeout must be positive number
- Rate limit must be positive integer
- Connection status reflects actual API accessibility

**State Transitions**:
- Disconnected → Connecting → Connected (successful auth)
- Connected → Disconnected (auth failure, network error)
- Any → Error (persistent failures)

### MCPTool
**Purpose**: MCP protocol tool definition for Joplin operations

**Fields**:
- `name`: Tool identifier (e.g., "search_notes", "get_note")
- `description`: Human-readable tool purpose
- `input_schema`: JSON schema for tool parameters
- `handler`: Function implementing tool logic

**Validation Rules**:
- Name must be valid MCP tool identifier
- Description required for client understanding
- Input schema must be valid JSON Schema
- Handler must be async callable

**Relationships**:
- Tools operate on Notes, Notebooks, and Connections
- Results returned as appropriate entity types