"""Tests for AgentCollection, AgentResource, APIKeyCollection, and OrgResource."""

import httpx

from tilde.models import Agent, APIKey, APIKeyCreated
from tilde.resources.agents import AgentCollection, AgentResource, APIKeyResource
from tilde.resources.organizations import OrgResource
from tilde.resources.repositories import OrgRepositoryCollection

AGENT_RESPONSE = {
    "id": "agent-1",
    "organization_id": "org-1",
    "name": "my-agent",
    "description": "Test agent",
    "metadata": {"env": "prod"},
    "inline_policy": "",
    "inline_policy_updated_at": None,
    "created_by_type": "user",
    "created_by": "user-1",
    "created_by_name": "alice",
    "created_at": "2025-08-01T12:00:00Z",
    "last_used_at": None,
}


class TestAgentCollection:
    def test_create(self, mock_api, client):
        """POST /organizations/test-org/agents."""
        route = mock_api.post("/organizations/test-org/agents").mock(
            return_value=httpx.Response(200, json=AGENT_RESPONSE)
        )
        agent = client.organization("test-org").agents.create(
            "my-agent", description="Test agent", metadata={"env": "prod"}
        )
        assert isinstance(agent, AgentResource)
        assert agent.name == "my-agent"
        assert agent.id == "agent-1"
        assert agent.description == "Test agent"
        assert agent.metadata == {"env": "prod"}
        assert route.called

    def test_get(self, mock_api, client):
        """GET /organizations/test-org/agents/my-agent."""
        mock_api.get("/organizations/test-org/agents/my-agent").mock(
            return_value=httpx.Response(200, json=AGENT_RESPONSE)
        )
        agent = client.organization("test-org").agents.get("my-agent")
        assert isinstance(agent, AgentResource)
        assert agent.name == "my-agent"
        assert agent.id == "agent-1"

    def test_list(self, mock_api, client):
        """GET /organizations/test-org/agents (paginated)."""
        mock_api.get("/organizations/test-org/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        AGENT_RESPONSE,
                        {**AGENT_RESPONSE, "id": "agent-2", "name": "other-agent"},
                    ],
                    "pagination": {"has_more": False, "next_offset": None},
                },
            )
        )
        agents = list(client.organization("test-org").agents.list())
        assert len(agents) == 2
        assert all(isinstance(a, Agent) for a in agents)
        assert agents[0].name == "my-agent"
        assert agents[1].name == "other-agent"

    def test_update(self, mock_api, client):
        """PUT /organizations/test-org/agents/my-agent."""
        updated = {**AGENT_RESPONSE, "description": "Updated"}
        route = mock_api.put("/organizations/test-org/agents/my-agent").mock(
            return_value=httpx.Response(200, json=updated)
        )
        agent = client.organization("test-org").agents.update("my-agent", description="Updated")
        assert isinstance(agent, AgentResource)
        assert agent.description == "Updated"
        assert route.called

    def test_update_inline_policy(self, mock_api, client):
        """PUT /organizations/test-org/agents/my-agent with inline_policy."""
        updated = {**AGENT_RESPONSE, "inline_policy": "allow read *"}
        route = mock_api.put("/organizations/test-org/agents/my-agent").mock(
            return_value=httpx.Response(200, json=updated)
        )
        agent = client.organization("test-org").agents.update(
            "my-agent", inline_policy="allow read *"
        )
        assert isinstance(agent, AgentResource)
        assert agent.inline_policy == "allow read *"
        assert route.called

    def test_delete(self, mock_api, client):
        """DELETE /organizations/test-org/agents/my-agent."""
        route = mock_api.delete("/organizations/test-org/agents/my-agent").mock(
            return_value=httpx.Response(204)
        )
        client.organization("test-org").agents.delete("my-agent")
        assert route.called


class TestAPIKeyCollection:
    def test_list(self, mock_api, client):
        """GET /organizations/test-org/agents/my-agent/auth/keys (paginated)."""
        mock_api.get("/organizations/test-org/agents/my-agent/auth/keys").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "key-1",
                            "name": "dev-key",
                            "description": "",
                            "token_hint": "cak-...abc",
                            "created_at": "2025-08-01T12:00:00Z",
                            "last_used_at": None,
                            "revoked_at": None,
                        }
                    ],
                    "pagination": {"has_more": False, "next_offset": None},
                },
            )
        )
        agent_res = AgentResource(client, "test-org", Agent.from_dict(AGENT_RESPONSE))
        keys = list(agent_res.api_keys.list())
        assert len(keys) == 1
        assert isinstance(keys[0], APIKey)
        assert keys[0].id == "key-1"
        assert keys[0].name == "dev-key"
        assert keys[0].token_hint == "cak-...abc"

    def test_create(self, mock_api, client):
        """POST /organizations/test-org/agents/my-agent/auth/keys."""
        route = mock_api.post("/organizations/test-org/agents/my-agent/auth/keys").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key-2",
                    "name": "new-key",
                    "description": "",
                    "token": "cak-full-secret-token",
                },
            )
        )
        agent_res = AgentResource(client, "test-org", Agent.from_dict(AGENT_RESPONSE))
        result = agent_res.api_keys.create("new-key")
        assert isinstance(result, APIKeyCreated)
        assert result.id == "key-2"
        assert result.token == "cak-full-secret-token"
        assert route.called

    def test_get(self, mock_api, client):
        """GET /organizations/test-org/agents/my-agent/auth/keys/key-1 (by ID)."""
        mock_api.get("/organizations/test-org/agents/my-agent/auth/keys/key-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key-1",
                    "name": "dev-key",
                    "description": "Development key",
                    "token_hint": "cak-...abc",
                    "created_at": "2025-08-01T12:00:00Z",
                    "last_used_at": None,
                    "revoked_at": None,
                },
            )
        )
        agent_res = AgentResource(client, "test-org", Agent.from_dict(AGENT_RESPONSE))
        key = agent_res.api_keys.get("key-1")
        assert isinstance(key, APIKeyResource)
        assert key.id == "key-1"
        assert key.name == "dev-key"
        assert key.token_hint == "cak-...abc"

    def test_revoke(self, mock_api, client):
        """get() by ID then revoke() DELETEs using that ID."""
        mock_api.get("/organizations/test-org/agents/my-agent/auth/keys/key-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "key-1",
                    "name": "dev-key",
                    "description": "",
                    "token_hint": "cak-...abc",
                    "created_at": "2025-08-01T12:00:00Z",
                    "last_used_at": None,
                    "revoked_at": None,
                },
            )
        )
        route = mock_api.delete("/organizations/test-org/agents/my-agent/auth/keys/key-1").mock(
            return_value=httpx.Response(204)
        )
        agent_res = AgentResource(client, "test-org", Agent.from_dict(AGENT_RESPONSE))
        key = agent_res.api_keys.get("key-1")
        key.revoke()
        assert route.called


class TestOrgResource:
    def test_agents_property(self, client):
        """OrgResource.agents returns AgentCollection."""
        org = client.organization("test-org")
        assert isinstance(org, OrgResource)
        assert isinstance(org.agents, AgentCollection)

    def test_repositories_property(self, client):
        """OrgResource.repositories returns OrgRepositoryCollection."""
        org = client.organization("test-org")
        assert isinstance(org.repositories, OrgRepositoryCollection)

    def test_list_repositories(self, mock_api, client):
        """GET /organizations/test-org/repositories (paginated)."""
        mock_api.get("/organizations/test-org/repositories").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "repo-1",
                            "organization_id": "org-1",
                            "name": "repo-one",
                            "description": "First repo",
                        }
                    ],
                    "pagination": {"has_more": False, "next_offset": None},
                },
            )
        )
        repos = list(client.organization("test-org").repositories.list())
        assert len(repos) == 1
        assert repos[0].name == "repo-one"

    def test_create_repository(self, mock_api, client):
        """POST /organizations/test-org/repositories."""
        route = mock_api.post("/organizations/test-org/repositories").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "repo-new",
                    "organization_id": "org-1",
                    "name": "my-repo",
                    "description": "A new repo",
                    "visibility": "private",
                    "created_by": "user-1",
                    "created_at": "2025-08-01T12:00:00Z",
                },
            )
        )
        from tilde.models import RepositoryData

        repo = client.organization("test-org").repositories.create(
            "my-repo", description="A new repo"
        )
        assert isinstance(repo, RepositoryData)
        assert repo.id == "repo-new"
        assert repo.name == "my-repo"
        assert repo.description == "A new repo"
        assert repo.visibility == "private"
        assert route.called
