"""Tests for the Repository resource."""

import httpx

from cerebral.models import RepositoryData
from cerebral.resources.sessions import Session


class TestRepository:
    def test_lazy_loading(self, mock_api, repo):
        """Accessing .description triggers GET /organizations/test-org/repositories/test-repo."""
        mock_api.get("/organizations/test-org/repositories/test-repo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "repo-1",
                    "organization_id": "org-1",
                    "name": "test-repo",
                    "description": "A test repository",
                    "visibility": "private",
                    "created_by": "user-1",
                    "created_at": "2025-01-15T10:00:00Z",
                },
            )
        )
        desc = repo.description
        assert desc == "A test repository"

    def test_properties(self, mock_api, repo):
        """All lazy-loaded properties are correctly populated."""
        mock_api.get("/organizations/test-org/repositories/test-repo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "repo-1",
                    "organization_id": "org-1",
                    "name": "test-repo",
                    "description": "desc",
                    "visibility": "public",
                    "created_by": "user-42",
                    "created_at": "2025-06-01T12:30:00Z",
                },
            )
        )
        assert repo.id == "repo-1"
        assert repo.description == "desc"
        assert repo.visibility == "public"
        assert repo.created_by == "user-42"
        assert repo.created_at is not None
        assert repo.created_at.year == 2025

    def test_update(self, mock_api, repo):
        """PUT /organizations/test-org/repositories/test-repo with json body."""
        route = mock_api.put("/organizations/test-org/repositories/test-repo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "repo-1",
                    "organization_id": "org-1",
                    "name": "test-repo",
                    "description": "updated desc",
                    "visibility": "private",
                    "created_by": "user-1",
                    "created_at": "2025-01-15T10:00:00Z",
                },
            )
        )
        result = repo.update(description="updated desc", visibility="private")
        assert isinstance(result, RepositoryData)
        assert result.description == "updated desc"
        assert route.called

    def test_delete(self, mock_api, repo):
        """DELETE /organizations/test-org/repositories/test-repo."""
        route = mock_api.delete("/organizations/test-org/repositories/test-repo").mock(
            return_value=httpx.Response(204)
        )
        repo.delete()
        assert route.called

    def test_session(self, mock_api, repo):
        """repo.session() creates a Session via POST .../sessions."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-repo-1"})
        )
        session = repo.session()
        assert isinstance(session, Session)
        assert session.session_id == "sess-repo-1"

    def test_attach(self, repo):
        """repo.attach() returns a Session without API call."""
        session = repo.attach("sess-existing")
        assert isinstance(session, Session)
        assert session.session_id == "sess-existing"
