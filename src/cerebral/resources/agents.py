"""Agent and API key resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerebral._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from cerebral.models import Agent, APIKey, APIKeyCreated

if TYPE_CHECKING:
    from datetime import datetime

    from cerebral.client import Client


class APIKeyCollection:
    """API key operations for an agent."""

    def __init__(self, client: Client, org: str, agent_name: str) -> None:
        self._client = client
        self._org = org
        self._agent_name = agent_name

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/agents/{self._agent_name}/auth/keys"

    def list(self, *, after: str | None = None) -> PaginatedIterator[APIKey]:
        """List API keys for this agent."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[APIKey]:
            params: dict[str, str | int] = {"amount": DEFAULT_PAGE_SIZE}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            data = self._client._get_json(self._base_path, params=params)
            items = [APIKey.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    def get(self, key_id: str) -> APIKeyResource:
        """Get an API key by ID.

        Args:
            key_id: The key's unique identifier (not the display name).

        The returned resource uses the same ``id`` for subsequent operations
        like :meth:`APIKeyResource.revoke`.
        """
        data = self._client._get_json(f"{self._base_path}/{key_id}")
        return APIKeyResource(self._client, self._base_path, APIKey.from_dict(data))

    def create(self, name: str) -> APIKeyCreated:
        """Create a new API key for this agent.

        The returned ``APIKeyCreated`` includes the full ``token`` which is
        only shown once.
        """
        data = self._client._post_json(self._base_path, json={"name": name})
        return APIKeyCreated.from_dict(data)


class APIKeyResource:
    """A single API key with data properties and a revoke method."""

    def __init__(self, client: Client, base_path: str, data: APIKey) -> None:
        self._client = client
        self._base_path = base_path
        self._data = data

    @property
    def id(self) -> str:
        return self._data.id

    @property
    def name(self) -> str:
        return self._data.name

    @property
    def description(self) -> str:
        return self._data.description

    @property
    def token_hint(self) -> str:
        return self._data.token_hint

    @property
    def created_at(self) -> datetime | None:
        return self._data.created_at

    @property
    def last_used_at(self) -> datetime | None:
        return self._data.last_used_at

    @property
    def revoked_at(self) -> datetime | None:
        return self._data.revoked_at

    def revoke(self) -> None:
        """Revoke this API key."""
        self._client._delete(f"{self._base_path}/{self._data.id}")


class AgentResource:
    """A single agent with data properties and sub-resource accessors."""

    def __init__(self, client: Client, org: str, data: Agent) -> None:
        self._client = client
        self._org = org
        self._data = data

    @property
    def name(self) -> str:
        return self._data.name

    @property
    def id(self) -> str:
        return self._data.id

    @property
    def description(self) -> str:
        return self._data.description

    @property
    def metadata(self) -> dict[str, str]:
        return self._data.metadata

    @property
    def created_at(self) -> datetime | None:
        return self._data.created_at

    @property
    def last_used_at(self) -> datetime | None:
        return self._data.last_used_at

    @property
    def api_keys(self) -> APIKeyCollection:
        """Access API key operations for this agent."""
        return APIKeyCollection(self._client, self._org, self._data.name)


class AgentCollection:
    """Agent operations for an organization."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/agents"

    def create(
        self,
        name: str,
        *,
        description: str = "",
        metadata: dict[str, str] | None = None,
    ) -> AgentResource:
        """Create a new agent."""
        body: dict[str, Any] = {"name": name, "description": description}
        if metadata is not None:
            body["metadata"] = metadata
        data = self._client._post_json(self._base_path, json=body)
        return AgentResource(self._client, self._org, Agent.from_dict(data))

    def get(self, name: str) -> AgentResource:
        """Get an agent by name."""
        data = self._client._get_json(f"{self._base_path}/{name}")
        return AgentResource(self._client, self._org, Agent.from_dict(data))

    def list(self, *, after: str | None = None) -> PaginatedIterator[Agent]:
        """List agents in the organization."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[Agent]:
            params: dict[str, str | int] = {"amount": DEFAULT_PAGE_SIZE}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            data = self._client._get_json(self._base_path, params=params)
            items = [Agent.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    def update(
        self,
        name: str,
        *,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AgentResource:
        """Update an agent."""
        body: dict[str, Any] = {}
        if description is not None:
            body["description"] = description
        if metadata is not None:
            body["metadata"] = metadata
        data = self._client._put_json(f"{self._base_path}/{name}", json=body)
        return AgentResource(self._client, self._org, Agent.from_dict(data))

    def delete(self, name: str) -> None:
        """Delete an agent."""
        self._client._delete(f"{self._base_path}/{name}")
