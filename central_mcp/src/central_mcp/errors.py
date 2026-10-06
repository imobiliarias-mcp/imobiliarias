"""Domain error hierarchy for central MCP providers."""

from enum import Enum


class ProviderErrorCode(str, Enum):
    """Allowed error codes for provider failures."""

    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INVALID_OUTPUT = "invalid_output"
    UPSTREAM_ERROR = "upstream_error"
    OUTPUT_TOO_LARGE = "output_too_large"
    UNSUPPORTED_FILTER = "unsupported_filter"


class ProviderError(Exception):
    """Raised when an agency provider fails execution."""

    def __init__(self, provider: str, code: str | ProviderErrorCode, message: str) -> None:
        self.provider = provider
        code_str = str(code.value if isinstance(code, ProviderErrorCode) else code)
        self._validate_code(code_str)
        self.code = code_str
        self.message = message
        super().__init__(f"[{provider}] {self.code}: {message}")

    @staticmethod
    def _validate_code(code: str) -> None:
        valid_codes = {item.value for item in ProviderErrorCode}
        if code not in valid_codes:
            raise ValueError(f"Invalid error code: {code}. Must be one of {valid_codes}")
