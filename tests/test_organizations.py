"""Tests for OrganizationCollection and MemberCollection."""

import httpx

from tilde.models import Membership, Organization


class TestOrganizationCollection:
    def test_create(self, mock_api, client):
        """POST /organizations."""
        route = mock_api.post("/organizations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "org-new",
                    "name": "new-org",
                    "display_name": "New Org",
                    "created_at": "2025-08-01T12:00:00Z",
                },
            )
        )
        org = client.organizations.create("new-org", "New Org")
        assert isinstance(org, Organization)
        assert org.id == "org-new"
        assert org.name == "new-org"
        assert org.display_name == "New Org"
        assert route.called

    def test_list(self, mock_api, client):
        """GET /organizations."""
        mock_api.get("/organizations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "org-1", "name": "org-one", "display_name": "Org One"},
                        {"id": "org-2", "name": "org-two", "display_name": "Org Two"},
                    ],
                },
            )
        )
        orgs = client.organizations.list()
        assert len(orgs) == 2
        assert all(isinstance(o, Organization) for o in orgs)
        assert orgs[0].name == "org-one"
        assert orgs[1].name == "org-two"

    def test_get(self, mock_api, client):
        """GET /organizations/test-org."""
        mock_api.get("/organizations/test-org").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "org-1",
                    "name": "test-org",
                    "display_name": "Test Organization",
                    "created_at": "2025-01-01T00:00:00Z",
                },
            )
        )
        org = client.organizations.get("test-org")
        assert isinstance(org, Organization)
        assert org.name == "test-org"
        assert org.display_name == "Test Organization"


class TestMemberCollection:
    def test_members_list(self, mock_api, client):
        """GET /organizations/test-org/members."""
        mock_api.get("/organizations/test-org/members").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "organization_id": "org-1",
                            "user_id": "user-1",
                            "role": "admin",
                            "username": "alice",
                        },
                        {
                            "organization_id": "org-1",
                            "user_id": "user-2",
                            "role": "member",
                            "username": "bob",
                        },
                    ],
                },
            )
        )
        members = client.organizations.members("test-org").list()
        assert len(members) == 2
        assert all(isinstance(m, Membership) for m in members)
        assert members[0].user_id == "user-1"
        assert members[0].role == "admin"
        assert members[1].username == "bob"

    def test_members_add(self, mock_api, client):
        """POST /organizations/test-org/members."""
        route = mock_api.post("/organizations/test-org/members").mock(
            return_value=httpx.Response(201)
        )
        client.organizations.members("test-org").add("user-3", role="member")
        assert route.called

    def test_members_remove(self, mock_api, client):
        """DELETE /organizations/test-org/members/{user_id}."""
        route = mock_api.delete("/organizations/test-org/members/user-3").mock(
            return_value=httpx.Response(204)
        )
        client.organizations.members("test-org").remove("user-3")
        assert route.called
