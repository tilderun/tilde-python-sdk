"""Role and API key resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tilde._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from tilde.models import APIKey, APIKeyCreated, Role

if TYPE_CHECKING:
    from datetime import datetime

    from tilde.client import Client


class RoleAPIKeyCollection:
    """API key operations for a role."""

    def __init__(self, client: Client, org: str, role_name: str) -> None:
        self._client = client
        self._org = org
        self._role_name = role_name

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/roles/{self._role_name}/auth/keys"

    def list(self, *, after: str | None = None) -> PaginatedIterator[APIKey]:
        """List API keys for this role."""
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

    def get(self, key_id: str) -> RoleAPIKeyResource:
        """Get an API key by ID."""
        data = self._client._get_json(f"{self._base_path}/{key_id}")
        return RoleAPIKeyResource(self._client, self._base_path, APIKey.from_dict(data))

    def create(self, name: str) -> APIKeyCreated:
        """Create a new API key for this role.

        The returned ``APIKeyCreated`` includes the full ``token`` which is
        only shown once.
        """
        data = self._client._post_json(self._base_path, json={"name": name})
        return APIKeyCreated.from_dict(data)


class RoleAPIKeyResource:
    """A single API key with data properties and a revoke method."""

    def __init__(self, client: Client, base_path: str, data: APIKey) -> None:
        self._client = client
        self._base_path = base_path
        self._data = data

    def __repr__(self) -> str:
        return f"RoleAPIKeyResource(name='{self._data.name}', id='{self._data.id}')"

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


class RoleResource:
    """A single role with data properties and sub-resource accessors."""

    def __init__(self, client: Client, org: str, data: Role) -> None:
        self._client = client
        self._org = org
        self._data = data

    def __repr__(self) -> str:
        return f"RoleResource(name='{self._data.name}')"

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
    def created_by(self) -> str:
        return self._data.created_by

    @property
    def created_by_name(self) -> str:
        return self._data.created_by_name

    @property
    def created_at(self) -> datetime | None:
        return self._data.created_at

    @property
    def last_used_at(self) -> datetime | None:
        return self._data.last_used_at

    @property
    def api_keys(self) -> RoleAPIKeyCollection:
        """Access API key operations for this role."""
        return RoleAPIKeyCollection(self._client, self._org, self._data.name)


class RoleCollection:
    """Role operations for an organization."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/roles"

    def create(self, name: str, *, description: str = "") -> RoleResource:
        """Create a new role."""
        body: dict[str, str] = {"name": name, "description": description}
        data = self._client._post_json(self._base_path, json=body)
        return RoleResource(self._client, self._org, Role.from_dict(data))

    def get(self, name: str) -> RoleResource:
        """Get a role by name."""
        data = self._client._get_json(f"{self._base_path}/{name}")
        return RoleResource(self._client, self._org, Role.from_dict(data))

    def list(self, *, after: str | None = None) -> PaginatedIterator[Role]:
        """List roles in the organization."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[Role]:
            params: dict[str, str | int] = {"amount": DEFAULT_PAGE_SIZE}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            data = self._client._get_json(self._base_path, params=params)
            items = [Role.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    def delete(self, name: str) -> None:
        """Delete a role."""
        self._client._delete(f"{self._base_path}/{name}")
