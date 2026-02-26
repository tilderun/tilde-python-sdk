"""Tests for PolicyCollection."""

import httpx
import pytest

from cerebral.models import (
    AttachmentRecord,
    EffectivePolicy,
    Policy,
    PolicyDetail,
    PolicySummary,
    ValidationResult,
)


class TestPolicyCollection:
    @pytest.fixture
    def policies(self, client):
        return client.organizations.policies("test-org")

    def test_create(self, mock_api, policies):
        """POST .../policies."""
        route = mock_api.post("/organizations/test-org/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pol-1",
                    "organization_id": "org-1",
                    "name": "deny-deletes",
                    "description": "Deny all deletes",
                    "rego": "package cerebral\ndefault allow = false",
                    "is_builtin": False,
                    "created_by": "user-1",
                    "created_at": "2025-04-01T10:00:00Z",
                },
            )
        )
        policy = policies.create(
            "deny-deletes",
            "package cerebral\ndefault allow = false",
            description="Deny all deletes",
        )
        assert isinstance(policy, Policy)
        assert policy.id == "pol-1"
        assert policy.name == "deny-deletes"
        assert route.called

    def test_list(self, mock_api, policies):
        """Paginated list of PolicySummary."""
        mock_api.get("/organizations/test-org/policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "pol-1",
                            "organization_id": "org-1",
                            "name": "deny-deletes",
                            "description": "",
                            "is_builtin": False,
                            "attachment_count": 2,
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        items = list(policies.list())
        assert len(items) == 1
        assert isinstance(items[0], PolicySummary)
        assert items[0].name == "deny-deletes"
        assert items[0].attachment_count == 2

    def test_get(self, mock_api, policies):
        """Returns PolicyDetail."""
        mock_api.get("/organizations/test-org/policies/pol-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policy": {
                        "id": "pol-1",
                        "organization_id": "org-1",
                        "name": "deny-deletes",
                        "description": "Deny all deletes",
                        "rego": "package cerebral",
                        "is_builtin": False,
                        "created_by": "user-1",
                    },
                    "attachments": [
                        {
                            "policy_id": "pol-1",
                            "policy_name": "deny-deletes",
                            "principal_type": "user",
                            "principal_id": "user-1",
                            "principal_name": "alice",
                            "attached_by": "admin-1",
                        },
                    ],
                },
            )
        )
        detail = policies.get("pol-1")
        assert isinstance(detail, PolicyDetail)
        assert detail.policy.name == "deny-deletes"
        assert len(detail.attachments) == 1
        assert detail.attachments[0].principal_id == "user-1"

    def test_update(self, mock_api, policies):
        """PUT .../policies/{id}."""
        route = mock_api.put("/organizations/test-org/policies/pol-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pol-1",
                    "organization_id": "org-1",
                    "name": "updated-policy",
                    "description": "Updated",
                    "rego": "package updated",
                    "is_builtin": False,
                    "created_by": "user-1",
                },
            )
        )
        result = policies.update("pol-1", name="updated-policy", rego="package updated")
        assert isinstance(result, Policy)
        assert result.name == "updated-policy"
        assert route.called

    def test_delete(self, mock_api, policies):
        """DELETE .../policies/{id}."""
        route = mock_api.delete("/organizations/test-org/policies/pol-1").mock(
            return_value=httpx.Response(204)
        )
        policies.delete("pol-1")
        assert route.called

    def test_validate(self, mock_api, policies):
        """POST .../policies:validate."""
        route = mock_api.post("/organizations/test-org/policies:validate").mock(
            return_value=httpx.Response(
                200,
                json={
                    "valid": True,
                    "errors": [],
                },
            )
        )
        result = policies.validate("package cerebral\ndefault allow = true")
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert result.errors == []
        assert route.called

    def test_attach(self, mock_api, policies):
        """POST .../policies/{id}/attachments."""
        route = mock_api.post("/organizations/test-org/policies/pol-1/attachments").mock(
            return_value=httpx.Response(201)
        )
        policies.attach("pol-1", principal_type="user", principal_id="user-1")
        assert route.called

    def test_detach(self, mock_api, policies):
        """DELETE .../policies/{id}/attachments."""
        route = mock_api.delete("/organizations/test-org/policies/pol-1/attachments").mock(
            return_value=httpx.Response(204)
        )
        policies.detach("pol-1", principal_type="user", principal_id="user-1")
        assert route.called

    def test_list_attachments(self, mock_api, policies):
        """GET .../attachments."""
        mock_api.get("/organizations/test-org/attachments").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "policy_id": "pol-1",
                            "policy_name": "deny-deletes",
                            "principal_type": "group",
                            "principal_id": "grp-1",
                            "principal_name": "engineers",
                            "attached_by": "admin-1",
                        },
                    ],
                },
            )
        )
        attachments = policies.list_attachments()
        assert len(attachments) == 1
        assert isinstance(attachments[0], AttachmentRecord)
        assert attachments[0].policy_id == "pol-1"
        assert attachments[0].principal_type == "group"

    def test_effective_policies(self, mock_api, policies):
        """GET .../effective-policies?user_id=..."""
        mock_api.get("/organizations/test-org/effective-policies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "policy_id": "pol-1",
                            "policy_name": "deny-deletes",
                            "is_builtin": False,
                            "source": "direct",
                            "source_name": "alice",
                        },
                    ],
                },
            )
        )
        effective = policies.effective_policies("user-1")
        assert len(effective) == 1
        assert isinstance(effective[0], EffectivePolicy)
        assert effective[0].policy_id == "pol-1"
        assert effective[0].source == "direct"
