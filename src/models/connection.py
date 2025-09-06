"""Connection model with validation."""

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, validator


class ConnectionState(str, Enum):
    """Enum for connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class Connection(BaseModel):
    """Manages authentication state and API configuration."""

    base_url: HttpUrl = Field(..., description="Joplin API endpoint URL")
    api_token: str = Field(..., description="Authentication token")
    timeout: float = Field(30.0, description="Request timeout in seconds")
    rate_limit: int = Field(60, description="Maximum requests per minute")
    is_connected: ConnectionState = Field(
        ConnectionState.DISCONNECTED, description="Current connection status"
    )
    last_error: str | None = Field(None, description="Last connection error message")
    retry_count: int = Field(0, description="Number of connection retry attempts")
    max_retries: int = Field(3, description="Maximum retry attempts")

    @validator("base_url", pre=True)
    def validate_base_url(cls, v) -> HttpUrl:
        """Validate base URL is valid HTTP/HTTPS URL."""
        if isinstance(v, str):
            # Ensure it has a scheme
            if not v.startswith(("http://", "https://")):
                v = f"http://{v}"
        return v

    @validator("api_token")
    def validate_api_token(cls, v: str) -> str:
        """Validate API token is required for authentication."""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("API token is required and must be non-empty")
        return v.strip()

    @validator("timeout")
    def validate_timeout(cls, v: float) -> float:
        """Validate timeout is positive number."""
        if not isinstance(v, int | float) or v <= 0:
            raise ValueError("Timeout must be a positive number")
        return float(v)

    @validator("rate_limit")
    def validate_rate_limit(cls, v: int) -> int:
        """Validate rate limit is positive integer."""
        if not isinstance(v, int) or v <= 0:
            raise ValueError("Rate limit must be a positive integer")
        return v

    @validator("is_connected")
    def validate_connection_status(cls, v: ConnectionState) -> ConnectionState:
        """Validate connection status."""
        if not isinstance(v, ConnectionState):
            if isinstance(v, str):
                try:
                    return ConnectionState(v.lower())
                except ValueError as ve:
                    valid_states = [state.value for state in ConnectionState]
                    raise ValueError(
                        f"Connection status must be one of: {valid_states}"
                    ) from ve
            else:
                raise ValueError(
                    "Connection status must be a ConnectionState enum or valid string"
                )
        return v

    @validator("retry_count", "max_retries")
    def validate_retry_counts(cls, v: int) -> int:
        """Validate retry counts are non-negative integers."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Retry counts must be non-negative integers")
        return v

    def transition_to(
        self, new_state: ConnectionState, error_message: str | None = None
    ) -> None:
        """Transition to a new connection state."""
        valid_transitions = {
            ConnectionState.DISCONNECTED: [ConnectionState.CONNECTING],
            ConnectionState.CONNECTING: [
                ConnectionState.CONNECTED,
                ConnectionState.ERROR,
                ConnectionState.DISCONNECTED,
            ],
            ConnectionState.CONNECTED: [
                ConnectionState.DISCONNECTED,
                ConnectionState.ERROR,
            ],
            ConnectionState.ERROR: [
                ConnectionState.CONNECTING,
                ConnectionState.DISCONNECTED,
            ],
        }

        if new_state not in valid_transitions.get(self.is_connected, []):
            raise ValueError(
                f"Invalid state transition from {self.is_connected} to {new_state}"
            )

        self.is_connected = new_state

        if new_state == ConnectionState.ERROR and error_message:
            self.last_error = error_message
        elif new_state == ConnectionState.CONNECTED:
            self.last_error = None
            self.retry_count = 0

    def can_retry(self) -> bool:
        """Check if connection can be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry counter."""
        self.retry_count += 1

    def reset_retry(self) -> None:
        """Reset retry counter."""
        self.retry_count = 0

    def get_connection_info(self) -> dict:
        """Get connection information for logging."""
        return {
            "base_url": str(self.base_url),
            "status": self.is_connected.value,
            "timeout": self.timeout,
            "rate_limit": self.rate_limit,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_error": self.last_error,
        }

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "forbid"
        use_enum_values = True
