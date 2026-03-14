"""Tests for Secrets resource (repository and agent secrets)."""

import httpx

from tilde.models import SecretEntry
from tilde.resources.secrets import SecretManager

REPO_SECRETS_PATH = "/organizations/test-org/repositories/test-repo/secrets"
AGENT_SECRETS_PATH = "/organizations/test-org/agents/data-pipeline/secrets"


class TestRepoSecretSet:
    def test_set_secret(self, mock_api, repo):
        """PUT .../secrets/{key} sets a repository secret."""
        route = mock_api.put(f"{REPO_SECRETS_PATH}/DB_PASSWORD").mock(
            return_value=httpx.Response(200, json={"key": "DB_PASSWORD"})
        )
        repo.secret.set("DB_PASSWORD", "supersecret")
        assert route.called
        import json

        payload = json.loads(route.calls[0].request.content)
        assert payload == {"value": "supersecret"}

    def test_set_secret_overwrite(self, mock_api, repo):
        """PUT .../secrets/{key} overwrites an existing secret."""
        mock_api.put(f"{REPO_SECRETS_PATH}/API_KEY").mock(
            return_value=httpx.Response(200, json={"key": "API_KEY"})
        )
        repo.secret.set("API_KEY", "new-value")


class TestRepoSecretGet:
    def test_get_secret(self, mock_api, repo):
        """GET .../secrets/{key} returns the decrypted value."""
        mock_api.get(f"{REPO_SECRETS_PATH}/DB_PASSWORD").mock(
            return_value=httpx.Response(
                200,
                json={"key": "DB_PASSWORD", "value": "supersecret"},
            )
        )
        value = repo.secret.get("DB_PASSWORD")
        assert value == "supersecret"


class TestRepoSecretDelete:
    def test_delete_secret(self, mock_api, repo):
        """DELETE .../secrets/{key} removes the secret."""
        route = mock_api.delete(f"{REPO_SECRETS_PATH}/DB_PASSWORD").mock(
            return_value=httpx.Response(204)
        )
        repo.secret.delete("DB_PASSWORD")
        assert route.called


class TestRepoSecretList:
    def test_list_secrets(self, mock_api, repo):
        """GET .../secrets lists secret metadata."""
        mock_api.get(REPO_SECRETS_PATH).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "key": "DB_PASSWORD",
                            "created_by_type": "user",
                            "created_by": "user-1",
                            "created_at": "2026-01-15T10:00:00+00:00",
                            "updated_at": "2026-01-15T10:00:00+00:00",
                        },
                        {
                            "key": "API_KEY",
                            "created_by_type": "agent",
                            "created_by": "agent-1",
                            "created_at": "2026-01-16T10:00:00+00:00",
                            "updated_at": "2026-01-16T10:00:00+00:00",
                        },
                    ]
                },
            )
        )
        secrets = repo.secrets()
        assert len(secrets) == 2
        assert all(isinstance(s, SecretEntry) for s in secrets)
        assert secrets[0].name == "DB_PASSWORD"
        assert secrets[0].created_by_type == "user"
        assert secrets[0].created_at is not None
        assert secrets[1].name == "API_KEY"

    def test_list_secrets_empty(self, mock_api, repo):
        """GET .../secrets returns empty list."""
        mock_api.get(REPO_SECRETS_PATH).mock(return_value=httpx.Response(200, json={"results": []}))
        secrets = repo.secrets()
        assert secrets == []


class TestAgentSecrets:
    def test_agent_secret_set(self, mock_api, client):
        """PUT .../agents/{name}/secrets/{key} sets an agent secret."""
        mock_api.get("/organizations/test-org/agents/data-pipeline").mock(
            return_value=httpx.Response(
                200,
                json={"id": "agent-1", "name": "data-pipeline", "organization_id": "org-1"},
            )
        )
        route = mock_api.put(f"{AGENT_SECRETS_PATH}/DB_PASSWORD").mock(
            return_value=httpx.Response(200, json={"key": "DB_PASSWORD"})
        )
        org = client.organization("test-org")
        agent = org.agents.get("data-pipeline")
        agent.secret.set("DB_PASSWORD", "supersecret")
        assert route.called

    def test_agent_secret_get(self, mock_api, client):
        """GET .../agents/{name}/secrets/{key} returns decrypted value."""
        mock_api.get("/organizations/test-org/agents/data-pipeline").mock(
            return_value=httpx.Response(
                200,
                json={"id": "agent-1", "name": "data-pipeline", "organization_id": "org-1"},
            )
        )
        mock_api.get(f"{AGENT_SECRETS_PATH}/DB_PASSWORD").mock(
            return_value=httpx.Response(
                200,
                json={"key": "DB_PASSWORD", "value": "supersecret"},
            )
        )
        org = client.organization("test-org")
        agent = org.agents.get("data-pipeline")
        value = agent.secret.get("DB_PASSWORD")
        assert value == "supersecret"

    def test_agent_secret_delete(self, mock_api, client):
        """DELETE .../agents/{name}/secrets/{key} removes the secret."""
        mock_api.get("/organizations/test-org/agents/data-pipeline").mock(
            return_value=httpx.Response(
                200,
                json={"id": "agent-1", "name": "data-pipeline", "organization_id": "org-1"},
            )
        )
        route = mock_api.delete(f"{AGENT_SECRETS_PATH}/DB_PASSWORD").mock(
            return_value=httpx.Response(204)
        )
        org = client.organization("test-org")
        agent = org.agents.get("data-pipeline")
        agent.secret.delete("DB_PASSWORD")
        assert route.called

    def test_agent_secrets_list(self, mock_api, client):
        """GET .../agents/{name}/secrets lists agent secret metadata."""
        mock_api.get("/organizations/test-org/agents/data-pipeline").mock(
            return_value=httpx.Response(
                200,
                json={"id": "agent-1", "name": "data-pipeline", "organization_id": "org-1"},
            )
        )
        mock_api.get(AGENT_SECRETS_PATH).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "key": "DB_PASSWORD",
                            "created_by_type": "user",
                            "created_by": "user-1",
                            "created_at": "2026-01-15T10:00:00+00:00",
                            "updated_at": "2026-01-15T10:00:00+00:00",
                        },
                    ]
                },
            )
        )
        org = client.organization("test-org")
        agent = org.agents.get("data-pipeline")
        secrets = agent.secrets()
        assert len(secrets) == 1
        assert secrets[0].name == "DB_PASSWORD"


class TestSecretEntryModel:
    def test_from_dict(self):
        """SecretEntry.from_dict() maps 'key' to 'name'."""
        entry = SecretEntry.from_dict(
            {
                "key": "MY_SECRET",
                "created_by_type": "user",
                "created_by": "user-1",
                "created_at": "2026-01-15T10:00:00+00:00",
                "updated_at": "2026-01-16T12:00:00+00:00",
            }
        )
        assert entry.name == "MY_SECRET"
        assert entry.created_by_type == "user"
        assert entry.created_at is not None
        assert entry.updated_at is not None

    def test_from_dict_minimal(self):
        """SecretEntry.from_dict() handles empty dict."""
        entry = SecretEntry.from_dict({})
        assert entry.name == ""
        assert entry.created_at is None

    def test_repr(self):
        """SecretEntry repr shows only non-default fields."""
        entry = SecretEntry(name="DB_PASSWORD")
        assert repr(entry) == "SecretEntry(name='DB_PASSWORD')"


class TestSecretManagerRepr:
    def test_repr(self, repo):
        """SecretManager repr shows its path."""
        mgr = repo.secret
        assert isinstance(mgr, SecretManager)
        assert "secrets" in repr(mgr)
