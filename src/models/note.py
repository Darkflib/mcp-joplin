"""Note model with validation."""


from pydantic import BaseModel, Field, validator


class Note(BaseModel):
    """Represents an individual Joplin note with all metadata and content."""

    id: str = Field(..., description="Unique identifier (Joplin note ID)")
    title: str = Field(..., description="Note title/name")
    body: str | None = Field(None, description="Full markdown content")
    parent_id: str = Field(..., description="Notebook ID containing this note")
    created_time: int = Field(..., description="Creation timestamp (Unix milliseconds)")
    updated_time: int = Field(
        ..., description="Last modification timestamp (Unix milliseconds)"
    )
    is_conflict: bool | None = Field(
        False, description="Boolean indicating sync conflicts"
    )
    markup_language: int | None = Field(
        1, description="Content format (1=Markdown, 2=HTML)"
    )
    tags: list[str] = Field(
        default_factory=list, description="List of tag names associated with note"
    )

    @validator("id")
    def validate_id(cls, v: str) -> str:
        """Validate ID is valid Joplin note ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("ID must be a non-empty string")
        # Joplin IDs are typically 32-character hex strings
        if len(v) != 32 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("ID must be valid Joplin note ID format (32-char hex)")
        return v

    @validator("title")
    def validate_title(cls, v: str) -> str:
        """Validate title is valid."""
        if not isinstance(v, str):
            raise ValueError("Title must be a string")
        return v

    @validator("body", pre=True)
    def validate_body(cls, v: str | None) -> str | None:
        """Validate body content as UTF-8."""
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Body must be a string or None")
        try:
            v.encode("utf-8")
        except UnicodeEncodeError as ue:
            raise ValueError("Body content must be valid UTF-8") from ue
        return v

    @validator("created_time", "updated_time")
    def validate_timestamps(cls, v: int) -> int:
        """Validate timestamps are positive integers."""
        if not isinstance(v, int) or v <= 0:
            raise ValueError("Timestamps must be positive integers")
        return v

    @validator("parent_id")
    def validate_parent_id(cls, v: str) -> str:
        """Validate parent ID references valid notebook."""
        if not v or not isinstance(v, str):
            raise ValueError("Parent ID must be a non-empty string")
        # Joplin notebook IDs are also 32-character hex strings
        if len(v) != 32 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("Parent ID must be valid Joplin notebook ID format")
        return v

    @validator("tags", pre=True)
    def parse_tags(cls, v) -> list[str]:
        """Parse tags from comma-separated string to list."""
        if isinstance(v, str):
            if not v.strip():
                return []
            return [tag.strip() for tag in v.split(",") if tag.strip()]
        elif isinstance(v, list):
            return [str(tag).strip() for tag in v if str(tag).strip()]
        elif v is None:
            return []
        else:
            raise ValueError("Tags must be string, list, or None")

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "forbid"
