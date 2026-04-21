"""SDK configuration and environment variable resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_ENDPOINT_URL = "https://tilde.run"
DEFAULT_SANDBOX_IMAGE = "ubuntu:22.04"

_ENV_API_KEY = "TILDE_API_KEY"  # pragma: allowlist secret
_ENV_ENDPOINT_URL = "TILDE_ENDPOINT_URL"
# TILDE_API_URL is the endpoint URL injected by the sandbox metadata stack,
# following the same ECS-style convention as TILDE_SANDBOX_CREDENTIALS_URI.
_ENV_API_URL = "TILDE_API_URL"
_ENV_DEFAULT_SANDBOX_IMAGE = "TILDE_DEFAULT_SANDBOX_IMAGE"

_CONFIG_FILE_KEY_API_KEY = "api_key"  # pragma: allowlist secret
_CONFIG_FILE_KEY_ENDPOINT_URL = "endpoint_url"


@dataclass(frozen=True)
class Configuration:
    """Resolved SDK configuration.

    ``api_key`` may be ``None`` at construction time; a
    :class:`~tilde.exceptions.ConfigurationError` is raised at request
    time if it is still unset.
    """

    endpoint_url: str
    api_key: str | None
    default_sandbox_image: str

    @property
    def base_url(self) -> str:
        """API base URL with ``/api/v1`` suffix."""
        return self.endpoint_url.rstrip("/") + "/api/v1"


def _default_config_path() -> Path:
    """Return the path to ``~/.tilde/config.yaml``.

    Resolved at call time so that tests patching ``$HOME`` take effect.
    """
    return Path.home() / ".tilde" / "config.yaml"


def _load_file_config() -> dict[str, str]:
    """Read ``~/.tilde/config.yaml`` written by the ``tilde`` CLI.

    Returns an empty dict when the file is missing, unreadable, or malformed —
    the SDK degrades gracefully to env vars and defaults rather than raising.
    Only string values for known keys are kept; other shapes are ignored.
    """
    path = _default_config_path()
    try:
        with path.open(encoding="utf-8") as f:
            data: Any = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, str] = {}
    for key in (_CONFIG_FILE_KEY_API_KEY, _CONFIG_FILE_KEY_ENDPOINT_URL):
        value = data.get(key)
        if isinstance(value, str) and value:
            result[key] = value
    return result


def resolve_config(
    *,
    endpoint_url: str | None = None,
    api_key: str | None = None,
    default_sandbox_image: str | None = None,
) -> Configuration:
    """Build a :class:`Configuration` from explicit params, env vars, and file.

    Resolution order: explicit parameter > environment variable >
    ``~/.tilde/config.yaml`` (written by ``tilde auth login``) > default.
    """
    file_cfg = _load_file_config()
    return Configuration(
        endpoint_url=(
            endpoint_url
            or os.environ.get(_ENV_ENDPOINT_URL)
            or os.environ.get(_ENV_API_URL)
            or file_cfg.get(_CONFIG_FILE_KEY_ENDPOINT_URL)
            or DEFAULT_ENDPOINT_URL
        ),
        api_key=(api_key or os.environ.get(_ENV_API_KEY) or file_cfg.get(_CONFIG_FILE_KEY_API_KEY)),
        default_sandbox_image=default_sandbox_image
        or os.environ.get(_ENV_DEFAULT_SANDBOX_IMAGE, DEFAULT_SANDBOX_IMAGE),
    )
