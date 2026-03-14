"""Tests for GroupCollection."""

import httpx
import pytest

from tilde.models import EffectiveGroup, Group, GroupDetail


class TestGroupCollection:
    @pytest.fixture
    def groups(self, client):
        return client.organizations.groups("test-org")

    def test_create(self, mock_api, groups):
        """POST .../groups."""
        route = mock_api.post("/organizations/test-org/groups").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "grp-1",
                    "organization_id": "org-1",
                    "name": "engineers",
                    "description": "Engineering team",
                    "created_by": "user-1",
                    "created_at": "2025-03-01T10:00:00Z",
                },
            )
        )
        group = groups.create("engineers", description="Engineering team")
        assert isinstance(group, Group)
        assert group.id == "grp-1"
        assert group.name == "engineers"
        assert route.called

    def test_list(self, mock_api, groups):
        """Paginated list of groups."""
        mock_api.get("/organizations/test-org/groups").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "grp-1",
                            "organization_id": "org-1",
                            "name": "eng",
                            "description": "",
                            "created_by": "u1",
                        },
                        {
                            "id": "grp-2",
                            "organization_id": "org-1",
                            "name": "qa",
                            "description": "",
                            "created_by": "u1",
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        items = list(groups.list())
        assert len(items) == 2
        assert all(isinstance(g, Group) for g in items)
        assert items[0].name == "eng"
        assert items[1].name == "qa"

    def test_get(self, mock_api, groups):
        """Returns GroupDetail."""
        mock_api.get("/organizations/test-org/groups/grp-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "group": {
                        "id": "grp-1",
                        "organization_id": "org-1",
                        "name": "engineers",
                        "description": "Engineering team",
                        "created_by": "user-1",
                        "created_at": "2025-03-01T10:00:00Z",
                    },
                    "members": [
                        {
                            "subject_type": "user",
                            "subject_id": "user-1",
                            "display_name": "Alice",
                            "username": "alice",
                        },
                    ],
                    "attachments": [],
                },
            )
        )
        detail = groups.get("grp-1")
        assert isinstance(detail, GroupDetail)
        assert detail.group.name == "engineers"
        assert len(detail.members) == 1
        assert detail.members[0].subject_id == "user-1"

    def test_update(self, mock_api, groups):
        """PUT .../groups/{id}."""
        route = mock_api.put("/organizations/test-org/groups/grp-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "grp-1",
                    "organization_id": "org-1",
                    "name": "engineering",
                    "description": "Updated desc",
                    "created_by": "user-1",
                },
            )
        )
        result = groups.update("grp-1", name="engineering", description="Updated desc")
        assert isinstance(result, Group)
        assert result.name == "engineering"
        assert route.called

    def test_delete(self, mock_api, groups):
        """DELETE .../groups/{id}."""
        route = mock_api.delete("/organizations/test-org/groups/grp-1").mock(
            return_value=httpx.Response(204)
        )
        groups.delete("grp-1")
        assert route.called

    def test_add_member(self, mock_api, groups):
        """POST .../groups/{id}/members."""
        route = mock_api.post("/organizations/test-org/groups/grp-1/members").mock(
            return_value=httpx.Response(201)
        )
        groups.add_member("grp-1", subject_type="user", subject_id="user-2")
        assert route.called

    def test_remove_member(self, mock_api, groups):
        """DELETE .../groups/{id}/members?subject_type=user&subject_id=..."""
        route = mock_api.delete("/organizations/test-org/groups/grp-1/members").mock(
            return_value=httpx.Response(204)
        )
        groups.remove_member("grp-1", subject_type="user", subject_id="user-2")
        assert route.called

    def test_effective_groups(self, mock_api, groups):
        """GET /organizations/test-org/effective-groups."""
        mock_api.get("/organizations/test-org/effective-groups").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "group_id": "grp-1",
                            "group_name": "engineers",
                            "description": "Engineering team",
                            "source": "direct",
                            "source_name": "engineers",
                        },
                        {
                            "group_id": "grp-2",
                            "group_name": "all-staff",
                            "description": "Everyone",
                            "source": "inherited",
                            "source_name": "engineers",
                        },
                    ],
                },
            )
        )
        result = groups.effective_groups(principal_type="user", principal_id="user-1")
        assert len(result) == 2
        assert all(isinstance(g, EffectiveGroup) for g in result)
        assert result[0].group_id == "grp-1"
        assert result[0].group_name == "engineers"
        assert result[0].source == "direct"
        assert result[1].group_id == "grp-2"
        assert result[1].source == "inherited"
