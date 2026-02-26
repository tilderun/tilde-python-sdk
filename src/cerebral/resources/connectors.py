"""Connector resources (org-level and repo-level)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerebral.models import ConnectorInfo

if TYPE_CHECKING:
    from cerebral.client import Client


class ConnectorCollection:
    """Org-level connector operations."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/connectors"

    def create(self, name: str, type: str, config: dict[str, Any]) -> ConnectorInfo:
        """Create a connector."""
        data = self._client._post_json(
            self._base_path,
            json={"name": name, "type": type, "config": config},
        )
        return ConnectorInfo.from_dict(data)

    def list(self) -> list[ConnectorInfo]:
        """List organization connectors (not paginated)."""
        data = self._client._get_json(self._base_path)
        return [ConnectorInfo.from_dict(d) for d in data.get("results", [])]

    def get(self, connector_id: str) -> ConnectorInfo:
        """Get a connector."""
        data = self._client._get_json(f"{self._base_path}/{connector_id}")
        return ConnectorInfo.from_dict(data)

    def delete(self, connector_id: str) -> None:
        """Delete a connector (soft delete)."""
        self._client._delete(f"{self._base_path}/{connector_id}")


class RepoConnectorCollection:
    """Repo-level connector attachment operations."""

    def __init__(self, client: Client, org: str, repo: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}/connectors"

    def attach(self, connector_id: str) -> None:
        """Attach a connector to this repository."""
        self._client._post(
            self._base_path,
            json={"connector_id": connector_id},
        )

    def detach(self, connector_id: str) -> None:
        """Detach a connector from this repository."""
        self._client._delete(f"{self._base_path}/{connector_id}")

    def list(self) -> list[ConnectorInfo]:
        """List connectors attached to this repository (not paginated)."""
        data = self._client._get_json(self._base_path)
        return [ConnectorInfo.from_dict(d) for d in data.get("results", [])]
