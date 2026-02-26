"""Organization resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerebral.models import Membership, Organization

if TYPE_CHECKING:
    from cerebral.client import Client
    from cerebral.resources.agents import AgentCollection
    from cerebral.resources.connectors import ConnectorCollection
    from cerebral.resources.groups import GroupCollection
    from cerebral.resources.policies import PolicyCollection
    from cerebral.resources.repositories import OrgRepositoryCollection
    from cerebral.resources.roles import RoleCollection


class MemberCollection:
    """Member operations for an organization."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    def list(self) -> list[Membership]:
        """List organization members (not paginated)."""
        data = self._client._get_json(f"/organizations/{self._org}/members")
        return [Membership.from_dict(d) for d in data.get("results", [])]

    def add(self, user_id: str, role: str = "member") -> None:
        """Add a member to the organization."""
        self._client._post(
            f"/organizations/{self._org}/members",
            json={"user_id": user_id, "role": role},
        )

    def remove(self, user_id: str) -> None:
        """Remove a member from the organization."""
        self._client._delete(f"/organizations/{self._org}/members/{user_id}")


class OrganizationCollection:
    """CRUD operations for organizations."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def create(self, name: str, display_name: str) -> Organization:
        """Create an organization."""
        data = self._client._post_json(
            "/organizations",
            json={"name": name, "display_name": display_name},
        )
        return Organization.from_dict(data)

    def list(self) -> list[Organization]:
        """List user's organizations (not paginated)."""
        data = self._client._get_json("/organizations")
        return [Organization.from_dict(d) for d in data.get("results", [])]

    def get(self, slug: str) -> Organization:
        """Get organization details."""
        data = self._client._get_json(f"/organizations/{slug}")
        return Organization.from_dict(data)

    def members(self, org: str) -> MemberCollection:
        """Access member operations for an organization."""
        return MemberCollection(self._client, org)

    def groups(self, org: str) -> GroupCollection:
        """Access group operations for an organization."""
        from cerebral.resources.groups import GroupCollection

        return GroupCollection(self._client, org)

    def policies(self, org: str) -> PolicyCollection:
        """Access policy operations for an organization."""
        from cerebral.resources.policies import PolicyCollection

        return PolicyCollection(self._client, org)

    def connectors(self, org: str) -> ConnectorCollection:
        """Access connector operations for an organization."""
        from cerebral.resources.connectors import ConnectorCollection

        return ConnectorCollection(self._client, org)

    def roles(self, org: str) -> RoleCollection:
        """Access role operations for an organization."""
        from cerebral.resources.roles import RoleCollection

        return RoleCollection(self._client, org)


class OrgResource:
    """A single organization with sub-resource accessors.

    Provides a fluent interface for accessing org-scoped resources::

        org = client.organization("my-org")
        org.agents.create("my-agent")
        org.repositories.list()
    """

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    @property
    def agents(self) -> AgentCollection:
        """Access agent operations for this organization."""
        from cerebral.resources.agents import AgentCollection

        return AgentCollection(self._client, self._org)

    @property
    def repositories(self) -> OrgRepositoryCollection:
        """Access repository listing for this organization."""
        from cerebral.resources.repositories import OrgRepositoryCollection

        return OrgRepositoryCollection(self._client, self._org)

    @property
    def members(self) -> MemberCollection:
        """Access member operations for this organization."""
        return MemberCollection(self._client, self._org)

    @property
    def groups(self) -> GroupCollection:
        """Access group operations for this organization."""
        from cerebral.resources.groups import GroupCollection

        return GroupCollection(self._client, self._org)

    @property
    def policies(self) -> PolicyCollection:
        """Access policy operations for this organization."""
        from cerebral.resources.policies import PolicyCollection

        return PolicyCollection(self._client, self._org)

    @property
    def connectors(self) -> ConnectorCollection:
        """Access connector operations for this organization."""
        from cerebral.resources.connectors import ConnectorCollection

        return ConnectorCollection(self._client, self._org)

    @property
    def roles(self) -> RoleCollection:
        """Access role operations for this organization."""
        from cerebral.resources.roles import RoleCollection

        return RoleCollection(self._client, self._org)
