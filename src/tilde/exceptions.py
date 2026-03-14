"""Exception hierarchy for the Tilde SDK.

All exceptions raised by the SDK inherit from ``TildeError``.
API errors carry the HTTP status code, error body fields, and request context.
"""

from __future__ import annotations


class TildeError(Exception):
    """Base exception for all Tilde SDK errors."""


class ConfigurationError(TildeError):
    """Missing or invalid SDK configuration (e.g. missing API key)."""


class TransportError(TildeError):
    """Network-level failure (DNS, timeout, connection refused).

    Wraps ``httpx.TransportError`` with a friendlier message.
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class SerializationError(TildeError):
    """Unexpected or malformed JSON in the API response."""


class APIError(TildeError):
    """Base for all HTTP API errors.

    Attributes:
        status_code: HTTP status code.
        message: Human-readable error message from the API.
        code: Machine-readable error code from the API.
        request_id: Request ID from the API error body.
        method: HTTP method of the failed request.
        url: URL of the failed request.
        response_text: Raw response body (truncated to 500 chars).
    """

    status_code: int
    message: str
    code: str
    request_id: str
    method: str
    url: str
    response_text: str

    def __init__(
        self,
        status_code: int,
        *,
        message: str = "",
        code: str = "",
        request_id: str = "",
        method: str = "",
        url: str = "",
        response_text: str = "",
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.code = code
        self.request_id = request_id
        self.method = method
        self.url = url
        self.response_text = response_text[:500]
        super().__init__(
            f"{method} {url} -> {status_code}: {message}" if method else f"{status_code}: {message}"
        )


class BadRequestError(APIError):
    """400 Bad Request."""


class AuthenticationError(APIError):
    """401 Unauthorized."""


class ForbiddenError(APIError):
    """403 Forbidden."""


class NotFoundError(APIError):
    """404 Not Found."""


class ConflictError(APIError):
    """409 Conflict."""


class GoneError(APIError):
    """410 Gone (e.g. connector deleted)."""


class PreconditionFailedError(APIError):
    """412 Precondition Failed (e.g. source changed since import)."""


class LockedError(APIError):
    """423 Locked (e.g. connector disabled)."""


class ServerError(APIError):
    """5xx Server Error."""


_STATUS_MAP: dict[int, type[APIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    410: GoneError,
    412: PreconditionFailedError,
    423: LockedError,
}


def api_error_for_status(
    status_code: int,
    *,
    message: str = "",
    code: str = "",
    request_id: str = "",
    method: str = "",
    url: str = "",
    response_text: str = "",
) -> APIError:
    """Create the appropriate ``APIError`` subclass for *status_code*."""
    cls = ServerError if status_code >= 500 else _STATUS_MAP.get(status_code, APIError)
    return cls(
        status_code,
        message=message,
        code=code,
        request_id=request_id,
        method=method,
        url=url,
        response_text=response_text,
    )
