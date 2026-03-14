"""Group resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tilde._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from tilde.models import EffectiveGroup, Group, GroupDetail

if TYPE_CHECKING:
    import builtins

    from tilde.client import Client


class GroupCollection:
    """CRUD operations for groups in an organization."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/groups"

    def create(self, name: str, description: str = "") -> Group:
        """Create a group."""
        body: dict[str, str] = {"name": name}
        if description:
            body["description"] = description
        data = self._client._post_json(self._base_path, json=body)
        return Group.from_dict(data)

    def list(self, *, after: str | None = None) -> PaginatedIterator[Group]:
        """List groups (paginated)."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[Group]:
            params: dict[str, str | int] = {}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            params["amount"] = DEFAULT_PAGE_SIZE
            data = self._client._get_json(self._base_path, params=params)
            items = [Group.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    def get(self, group_id: str) -> GroupDetail:
        """Get a group with members and attachments."""
        data = self._client._get_json(f"{self._base_path}/{group_id}")
        return GroupDetail.from_dict(data)

    def update(
        self,
        group_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Group:
        """Update a group's name or description."""
        body: dict[str, str] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        data = self._client._put_json(f"{self._base_path}/{group_id}", json=body)
        return Group.from_dict(data)

    def delete(self, group_id: str) -> None:
        """Delete a group."""
        self._client._delete(f"{self._base_path}/{group_id}")

    def add_member(self, group_id: str, subject_type: str, subject_id: str) -> None:
        """Add a member (user or group) to a group."""
        self._client._post(
            f"{self._base_path}/{group_id}/members",
            json={"subject_type": subject_type, "subject_id": subject_id},
        )

    def remove_member(self, group_id: str, subject_type: str, subject_id: str) -> None:
        """Remove a member from a group."""
        self._client._delete(
            f"{self._base_path}/{group_id}/members",
            params={"subject_type": subject_type, "subject_id": subject_id},
        )

    def effective_groups(
        self, principal_type: str, principal_id: str
    ) -> builtins.list[EffectiveGroup]:
        """Get effective groups for a principal.

        Args:
            principal_type: Type of principal (e.g. ``"user"``).
            principal_id: ID of the principal.
        """
        data = self._client._get_json(
            f"/organizations/{self._org}/effective-groups",
            params={"principal_type": principal_type, "principal_id": principal_id},
        )
        return [EffectiveGroup.from_dict(d) for d in data.get("results", [])]
