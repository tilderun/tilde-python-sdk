"""Tests for ConnectorCollection and RepoConnectorCollection."""

import httpx
import pytest

from tilde.models import ConnectorInfo


class TestConnectorCollection:
    """Org-level connector operations."""

    @pytest.fixture
    def connectors(self, client):
        return client.organizations.connectors("test-org")

    def test_create(self, mock_api, connectors):
        """POST .../connectors."""
        route = mock_api.post("/organizations/test-org/connectors").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "conn-1",
                    "name": "my-s3",
                    "type": "s3",
                    "disabled": False,
                    "created_at": "2025-06-01T10:00:00Z",
                },
            )
        )
        result = connectors.create("my-s3", "s3", {"bucket": "my-bucket", "region": "us-east-1"})
        assert isinstance(result, ConnectorInfo)
        assert result.id == "conn-1"
        assert result.name == "my-s3"
        assert result.type == "s3"
        assert route.called

    def test_list(self, mock_api, connectors):
        """GET .../connectors."""
        mock_api.get("/organizations/test-org/connectors").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "conn-1", "name": "my-s3", "type": "s3", "disabled": False},
                        {"id": "conn-2", "name": "my-gcs", "type": "gcs", "disabled": False},
                    ],
                },
            )
        )
        items = connectors.list()
        assert len(items) == 2
        assert all(isinstance(c, ConnectorInfo) for c in items)
        assert items[0].name == "my-s3"
        assert items[1].name == "my-gcs"

    def test_get(self, mock_api, connectors):
        """GET .../connectors/{id}."""
        mock_api.get("/organizations/test-org/connectors/conn-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "conn-1",
                    "name": "my-s3",
                    "type": "s3",
                    "disabled": False,
                    "created_at": "2025-06-01T10:00:00Z",
                },
            )
        )
        result = connectors.get("conn-1")
        assert isinstance(result, ConnectorInfo)
        assert result.id == "conn-1"

    def test_delete(self, mock_api, connectors):
        """DELETE .../connectors/{id}."""
        route = mock_api.delete("/organizations/test-org/connectors/conn-1").mock(
            return_value=httpx.Response(204)
        )
        connectors.delete("conn-1")
        assert route.called


class TestRepoConnectorCollection:
    """Repo-level connector attachment operations."""

    def test_attach(self, mock_api, repo):
        """POST .../repositories/test-repo/connectors."""
        route = mock_api.post("/organizations/test-org/repositories/test-repo/connectors").mock(
            return_value=httpx.Response(201)
        )
        repo.connectors.attach("conn-1")
        assert route.called

    def test_detach(self, mock_api, repo):
        """DELETE .../repositories/test-repo/connectors/{id}."""
        route = mock_api.delete(
            "/organizations/test-org/repositories/test-repo/connectors/conn-1"
        ).mock(return_value=httpx.Response(204))
        repo.connectors.detach("conn-1")
        assert route.called

    def test_list(self, mock_api, repo):
        """GET .../repositories/test-repo/connectors."""
        mock_api.get("/organizations/test-org/repositories/test-repo/connectors").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "conn-1", "name": "my-s3", "type": "s3", "disabled": False},
                    ],
                },
            )
        )
        items = repo.connectors.list()
        assert len(items) == 1
        assert isinstance(items[0], ConnectorInfo)
        assert items[0].id == "conn-1"
