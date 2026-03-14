"""SDK configuration and environment variable resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_ENDPOINT_URL = "https://tilde.run"

_ENV_API_KEY = "TILDE_API_KEY"  # pragma: allowlist secret
_ENV_ENDPOINT_URL = "TILDE_ENDPOINT_URL"


@dataclass(frozen=True)
class Configuration:
    """Resolved SDK configuration.

    ``api_key`` may be ``None`` at construction time; a
    :class:`~tilde.exceptions.ConfigurationError` is raised at request
    time if it is still unset.
    """

    endpoint_url: str
    api_key: str | None

    @property
    def base_url(self) -> str:
        """API base URL with ``/api/v1`` suffix."""
        return self.endpoint_url.rstrip("/") + "/api/v1"


def resolve_config(
    *,
    endpoint_url: str | None = None,
    api_key: str | None = None,
) -> Configuration:
    """Build a :class:`Configuration` from explicit params and env vars.

    Resolution order: explicit parameter > environment variable > default.
    """
    return Configuration(
        endpoint_url=endpoint_url or os.environ.get(_ENV_ENDPOINT_URL, DEFAULT_ENDPOINT_URL),
        api_key=api_key or os.environ.get(_ENV_API_KEY),
    )
