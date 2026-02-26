"""Tests for RoleCollection, RoleResource, RoleAPIKeyCollection, and OrgResource."""

import httpx

from cerebral.models import APIKey, APIKeyCreated, Role
from cerebral.resources.organizations import OrgResource
from cerebral.resources.roles import RoleAPIKeyResource, RoleCollection, RoleResource

ROLE_RESPONSE = {
    "id": "role-1",
    "organization_id": "org-1",
    "name": "my-role",
    "description": "Test role",
    "created_by": "user-1",
    "created_by_name": "Alice",
    "created_at": "2025-08-01T12:00:00Z",
    "last_used_at": None,
}


class TestRoleCollection:
    def test_create(self, mock_api, client):
        """POST /organizations/test-org/roles."""
        route = mock_api.post("/organizations/test-org/roles").mock(
            return_value=httpx.Response(200, json=ROLE_RESPONSE)
        )
        role = client.organization("test-org").roles.create("my-role", description="Test role")
        assert isinstance(role, RoleResource)
        assert role.name == "my-role"
        assert role.id == "role-1"
        assert role.description == "Test role"
        assert role.created_by == "user-1"
        assert role.created_by_name == "Alice"
        assert route.called

    def test_get(self, mock_api, client):
        """GET /organizations/test-org/roles/my-role."""
        mock_api.get("/organizations/test-org/roles/my-role").mock(
            return_value=httpx.Response(200, json=ROLE_RESPONSE)
        )
        role = client.organization("test-org").roles.get("my-role")
        assert isinstance(role, RoleResource)
        assert role.name == "my-role"
        assert role.id == "role-1"

    def test_list(self, mock_api, client):
        """GET /organizations/test-org/roles (paginated)."""
        mock_api.get("/organizations/test-org/roles").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        ROLE_RESPONSE,
                        {**ROLE_RESPONSE, "id": "role-2", "name": "other-role"},
                    ],
                    "pagination": {"has_more": False, "next_offset": None},
                },
            )
        )
        roles = list(client.organization("test-org").roles.list())
        assert len(roles) == 2
        assert all(isinstance(r, Role) for r in roles)
        assert roles[0].name == "my-role"
        assert roles[1].name == "other-role"

    def test_delete(self, mock_api, client):
        """DELETE /organizations/test-org/roles/my-role."""
        route = mock_api.delete("/organizations/test-org/roles/my-role").mock(
            return_value=httpx.Response(204)
        )
        client.organization("test-org").roles.delete("my-role")
        assert route.called


class TestRoleAPIKeyCollection:
    def test_list(self, mock_api, client):
        """GET /organizations/test-org/roles/my-role/auth/keys (paginated)."""
        mock_api.get("/organizations/test-org/roles/my-role/auth/keys").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "key-1",
                            "name": "dev-key",
                            "description": "",
                            "token_hint": "crk-...abc",
                            "created_at": "2025-08-01T12:00:00Z",
                            "last_used_at": None,
                            "revoked_at": None,
                        }
                    ],
                    "pagination": {"has_more": False, "next_offset": None},
                },
            )
        )
        role_res = RoleResource(client, "test-org", Role.from_dict(ROLE_RESPONSE))
        keys = list(role_res.api_keys.list())
        assert len(keys) == 1
        assert isinstance(keys[0], APIKey)
        assert keys[0].id == "key-1"
        assert keys[0].name == "dev-key"
        assert keys[0].token_hint == "crk-...abc"

    def test_create(self, mock_api, client):
        """POST /organizations/test-org/roles/my-role/auth/keys."""
        route = mock_api.post("/organizations/test-org/roles/my-role/auth/keys").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key-2",
                    "name": "new-key",
                    "description": "",
                    "token": "crk-full-secret-token",
                },
            )
        )
        role_res = RoleResource(client, "test-org", Role.from_dict(ROLE_RESPONSE))
        result = role_res.api_keys.create("new-key")
        assert isinstance(result, APIKeyCreated)
        assert result.id == "key-2"
        assert result.token == "crk-full-secret-token"
        assert route.called

    def test_get(self, mock_api, client):
        """GET /organizations/test-org/roles/my-role/auth/keys/key-1 (by ID)."""
        mock_api.get("/organizations/test-org/roles/my-role/auth/keys/key-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key-1",
                    "name": "dev-key",
                    "description": "Development key",
                    "token_hint": "crk-...abc",
                    "created_at": "2025-08-01T12:00:00Z",
                    "last_used_at": None,
                    "revoked_at": None,
                },
            )
        )
        role_res = RoleResource(client, "test-org", Role.from_dict(ROLE_RESPONSE))
        key = role_res.api_keys.get("key-1")
        assert isinstance(key, RoleAPIKeyResource)
        assert key.id == "key-1"
        assert key.name == "dev-key"
        assert key.token_hint == "crk-...abc"

    def test_revoke(self, mock_api, client):
        """get() by ID then revoke() DELETEs using that ID."""
        mock_api.get("/organizations/test-org/roles/my-role/auth/keys/key-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key-1",
                    "name": "dev-key",
                    "description": "",
                    "token_hint": "crk-...abc",
                    "created_at": "2025-08-01T12:00:00Z",
                    "last_used_at": None,
                    "revoked_at": None,
                },
            )
        )
        route = mock_api.delete("/organizations/test-org/roles/my-role/auth/keys/key-1").mock(
            return_value=httpx.Response(204)
        )
        role_res = RoleResource(client, "test-org", Role.from_dict(ROLE_RESPONSE))
        key = role_res.api_keys.get("key-1")
        key.revoke()
        assert route.called


class TestOrgRolesResource:
    def test_roles_property(self, client):
        """OrgResource.roles returns RoleCollection."""
        org = client.organization("test-org")
        assert isinstance(org, OrgResource)
        assert isinstance(org.roles, RoleCollection)
