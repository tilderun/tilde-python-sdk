"""Secret management for repositories and agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tilde.models import SecretEntry

if TYPE_CHECKING:
    from tilde.client import Client


class SecretManager:
    """Manage secrets at a given API path.

    Used by both :class:`~tilde.resources.repositories.Repository` and
    :class:`~tilde.resources.agents.AgentResource` to provide a uniform
    interface for secret operations::

        repo.secret.set("DB_PASSWORD", "supersecret")
        value = repo.secret.get("DB_PASSWORD")
        repo.secret.delete("DB_PASSWORD")
    """

    def __init__(self, client: Client, base_path: str) -> None:
        self._client = client
        self._base_path = base_path

    def __repr__(self) -> str:
        return f"SecretManager(path='{self._base_path}')"

    def set(self, key: str, value: str) -> None:
        """Create or update a secret.

        Args:
            key: Secret key name.
            value: Secret value (UTF-8 string, max 64 KiB).
        """
        self._client._put_json(f"{self._base_path}/{key}", json={"value": value})

    def get(self, key: str) -> str:
        """Get a decrypted secret value.

        Args:
            key: Secret key name.

        Returns:
            The secret value as a string.
        """
        data = self._client._get_json(f"{self._base_path}/{key}")
        return str(data.get("value", ""))

    def delete(self, key: str) -> None:
        """Delete a secret.

        Args:
            key: Secret key name.
        """
        self._client._delete(f"{self._base_path}/{key}")

    def list(self) -> list[SecretEntry]:
        """List secrets (keys and metadata only, no values)."""
        data = self._client._get_json(self._base_path)
        return [SecretEntry.from_dict(d) for d in data.get("results", [])]
