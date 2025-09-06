"""MCPTool model with validation."""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field, validator


class MCPTool(BaseModel):
    """MCP protocol tool definition for Joplin operations."""

    name: str = Field(
        ..., description="Tool identifier (e.g., 'search_notes', 'get_note')"
    )
    description: str = Field(..., description="Human-readable tool purpose")
    input_schema: dict[str, Any] = Field(
        ..., description="JSON schema for tool parameters"
    )
    output_schema: dict[str, Any] | None = Field(
        None, description="JSON schema for tool output"
    )
    handler: Callable[[dict[str, Any]], Awaitable[Any]] | None = Field(
        None, description="Function implementing tool logic"
    )

    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate name is valid MCP tool identifier."""
        if not v or not isinstance(v, str):
            raise ValueError("Tool name must be a non-empty string")

        # MCP tool names should be valid identifiers (letters, numbers, underscores)
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Tool name must contain only letters, numbers, hyphens, and underscores"
            )

        # Should not start with number
        if v[0].isdigit():
            raise ValueError("Tool name cannot start with a number")

        return v

    @validator("description")
    def validate_description(cls, v: str) -> str:
        """Validate description is required for client understanding."""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Tool description is required and must be non-empty")
        return v.strip()

    @validator("input_schema")
    def validate_input_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate input schema is valid JSON Schema."""
        if not isinstance(v, dict):
            raise ValueError("Input schema must be a dictionary")

        # Basic JSON Schema validation
        if "type" not in v:
            raise ValueError("Input schema must have a 'type' field")

        # For object types, should have properties
        if v.get("type") == "object" and "properties" not in v:
            raise ValueError("Object schema must have 'properties' field")

        return v

    @validator("output_schema")
    def validate_output_schema(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate output schema is valid JSON Schema if provided."""
        if v is None:
            return v

        if not isinstance(v, dict):
            raise ValueError("Output schema must be a dictionary")

        # Basic JSON Schema validation
        if "type" not in v:
            raise ValueError("Output schema must have a 'type' field")

        return v

    @validator("handler")
    def validate_handler(cls, v: Callable | None) -> Callable | None:
        """Validate handler is async callable if provided."""
        if v is None:
            return v

        if not callable(v):
            raise ValueError("Handler must be callable")

        # Check if it's a coroutine function (async)
        import inspect

        if not inspect.iscoroutinefunction(v):
            raise ValueError("Handler must be an async function")

        return v

    def validate_arguments(self, arguments: dict[str, Any]) -> bool:
        """Validate arguments against input schema."""
        # This is a simplified validation - in production you'd use jsonschema library
        schema = self.input_schema

        if schema.get("type") != "object":
            return True  # Skip validation for non-object schemas

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Check required fields
        for field in required:
            if field not in arguments:
                raise ValueError(f"Missing required field: {field}")

        # Check field types (basic validation)
        for field, value in arguments.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type and not self._validate_json_type(value, expected_type):
                    raise ValueError(
                        f"Field '{field}' has invalid type, expected {expected_type}"
                    )

        return True

    def _validate_json_type(self, value: Any, json_type: str) -> bool:
        """Validate value matches JSON schema type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        expected_python_type = type_mapping.get(json_type)
        if expected_python_type is None:
            return True  # Unknown type, skip validation

        return isinstance(value, expected_python_type)

    async def execute(self, arguments: dict[str, Any]) -> Any:
        """Execute the tool with given arguments."""
        if self.handler is None:
            raise ValueError("No handler configured for this tool")

        # Validate arguments
        self.validate_arguments(arguments)

        # Execute handler
        return await self.handler(arguments)

    def to_mcp_definition(self) -> dict[str, Any]:
        """Convert to MCP tool definition format."""
        definition = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

        if self.output_schema:
            definition["outputSchema"] = self.output_schema

        return definition

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "forbid"
        arbitrary_types_allowed = True  # Allow Callable type
