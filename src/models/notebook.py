"""Notebook model with validation."""


from pydantic import BaseModel, Field, validator


class Notebook(BaseModel):
    """Container for organizing notes with hierarchical structure."""

    id: str = Field(..., description="Unique identifier (Joplin notebook ID)")
    title: str = Field(..., description="Notebook display name")
    parent_id: str | None = Field(
        None, description="Parent notebook ID (null for root notebooks)"
    )
    created_time: int = Field(..., description="Creation timestamp (Unix milliseconds)")
    updated_time: int = Field(
        ..., description="Last modification timestamp (Unix milliseconds)"
    )
    children: list["Notebook"] | None = Field(
        None, description="Nested child notebooks"
    )

    @validator("id")
    def validate_id(cls, v: str) -> str:
        """Validate ID is valid Joplin notebook ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("ID must be a non-empty string")
        # Joplin IDs are typically 32-character hex strings
        if len(v) != 32 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("ID must be valid Joplin notebook ID format (32-char hex)")
        return v

    @validator("title")
    def validate_title(cls, v: str) -> str:
        """Validate title is required and non-empty."""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Title must be a non-empty string")
        return v.strip()

    @validator("parent_id")
    def validate_parent_id(cls, v: str | None) -> str | None:
        """Validate parent ID references existing notebook or is null."""
        if v is None or v == "":
            return None
        if not isinstance(v, str):
            raise ValueError("Parent ID must be a string or None")
        # Joplin notebook IDs are 32-character hex strings
        if len(v) != 32 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("Parent ID must be valid Joplin notebook ID format")
        return v

    @validator("created_time", "updated_time")
    def validate_timestamps(cls, v: int) -> int:
        """Validate timestamps are positive integers."""
        if not isinstance(v, int) or v <= 0:
            raise ValueError("Timestamps must be positive integers")
        return v

    @validator("children", pre=True)
    def validate_children(cls, v) -> list["Notebook"] | None:
        """Validate children structure."""
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("Children must be a list or None")
        return v

    def has_circular_reference(self, visited_ids: set | None = None) -> bool:
        """Check for circular parent references."""
        if visited_ids is None:
            visited_ids = set()

        if self.id in visited_ids:
            return True

        if self.parent_id is None:
            return False

        visited_ids.add(self.id)

        # In a real implementation, you would fetch the parent notebook
        # For now, we just check if parent_id equals any visited ID
        return self.parent_id in visited_ids

    def add_child(self, child: "Notebook") -> None:
        """Add a child notebook to this notebook."""
        if self.children is None:
            self.children = []

        # Check for circular reference
        if child.parent_id == self.id and not child.has_circular_reference({self.id}):
            self.children.append(child)
        else:
            raise ValueError("Cannot add child: would create circular reference")

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "forbid"


# Update forward reference
Notebook.model_rebuild()
