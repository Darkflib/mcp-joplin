"""SearchResult model with validation."""

from enum import Enum

from pydantic import BaseModel, Field, validator


class MatchType(str, Enum):
    """Enum for where match occurred."""

    TITLE = "title"
    BODY = "body"
    TAGS = "tags"
    MIXED = "mixed"


class SearchResultItem(BaseModel):
    """Individual search result item."""

    note_id: str = Field(..., description="ID of the matching note")
    title: str = Field(..., description="Note title")
    snippet: str = Field(..., description="Content excerpt showing match context")
    relevance_score: float = Field(..., description="Relevance score (0.0-1.0)")

    @validator("note_id")
    def validate_note_id(cls, v: str) -> str:
        """Validate note ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Note ID must be a non-empty string")
        if len(v) != 32 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("Note ID must be 32-character hexadecimal string")
        return v.lower()

    @validator("relevance_score")
    def validate_score(cls, v: float) -> float:
        """Validate score is between 0.0 and 1.0."""
        if not isinstance(v, int | float):
            raise ValueError("Relevance score must be a number")
        score = float(v)
        if not (0.0 <= score <= 1.0):
            raise ValueError("Relevance score must be between 0.0 and 1.0")
        return score

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "forbid"


class MatchContext(BaseModel):
    """Represents context around a match."""

    match_type: MatchType = Field(..., description="Type of match (title, body, etc.)")
    match_text: str = Field(..., description="Actual text that matched")
    context_before: str = Field(default="", description="Text context before the match")
    context_after: str = Field(default="", description="Text context after the match")
    position: int = Field(default=0, description="Character position of match")
    score: float = Field(..., description="Match strength score (0.0-1.0)")

    @validator("match_text")
    def validate_match_text(cls, v: str) -> str:
        """Validate match text is not empty."""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Match text must be a non-empty string")
        return v.strip()

    @validator("context_before", "context_after")
    def validate_context(cls, v: str) -> str:
        """Validate context strings."""
        if not isinstance(v, str):
            raise ValueError("Context must be a string")
        return v

    @validator("position")
    def validate_position(cls, v: int) -> int:
        """Validate position is non-negative."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Position must be a non-negative integer")
        return v

    @validator("score")
    def validate_score(cls, v: float) -> float:
        """Validate score is between 0.0 and 1.0 inclusive."""
        if not isinstance(v, int | float):
            raise ValueError("Score must be a number")
        score = float(v)
        if not (0.0 <= score <= 1.0):
            raise ValueError("Score must be between 0.0 and 1.0")
        return score

    @validator("match_type")
    def validate_match_type(cls, v: MatchType) -> MatchType:
        """Validate match type is valid enum value."""
        if not isinstance(v, MatchType):
            if isinstance(v, str):
                try:
                    return MatchType(v.lower())
                except ValueError as ve:
                    valid_types = [mt.value for mt in MatchType]
                    raise ValueError(
                        f"Match type must be one of: {valid_types}"
                    ) from ve
            else:
                raise ValueError("Match type must be a MatchType enum or valid string")
        return v

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "forbid"
        use_enum_values = True


class SearchResult(BaseModel):
    """Complete search result with metadata."""

    query: str = Field(..., description="Original search query")
    items: list[SearchResultItem] = Field(
        default_factory=list, description="List of matching notes"
    )
    total_count: int = Field(0, description="Total number of results found")
    execution_time_ms: float = Field(
        0.0, description="Query execution time in milliseconds"
    )
    has_more: bool = Field(False, description="Whether more results are available")
    match_contexts: list[MatchContext] = Field(
        default_factory=list, description="Detailed match contexts"
    )

    @validator("query")
    def validate_query(cls, v: str) -> str:
        """Validate query is not empty."""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Query must be a non-empty string")
        return v.strip()

    @validator("total_count")
    def validate_total_count(cls, v: int) -> int:
        """Validate total count is non-negative."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Total count must be a non-negative integer")
        return v

    @validator("execution_time_ms")
    def validate_execution_time(cls, v: float) -> float:
        """Validate execution time is non-negative."""
        if not isinstance(v, int | float) or v < 0:
            raise ValueError("Execution time must be a non-negative number")
        return float(v)

    def add_match_context(self, context: MatchContext) -> None:
        """Add match context to the result."""
        self.match_contexts.append(context)

    def get_summary(self) -> dict[str, any]:
        """Get summary information about the search results."""
        return {
            "query": self.query,
            "total_results": self.total_count,
            "returned_results": len(self.items),
            "execution_time_ms": self.execution_time_ms,
            "has_more": self.has_more,
            "match_types": {ctx.match_type.value for ctx in self.match_contexts},
        }

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "forbid"
