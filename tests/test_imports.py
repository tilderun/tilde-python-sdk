"""Tests for ImportResource."""

import httpx

from cerebral.models import ImportJob


class TestImportResource:
    def test_from_connector(self, mock_api, repo):
        """POST .../import with connector_id returns job_id."""
        route = mock_api.post("/organizations/test-org/repositories/test-repo/import").mock(
            return_value=httpx.Response(202, json={"job_id": "job-abc-123"})
        )
        job_id = repo.imports.from_connector(
            connector_id="conn-1",
            destination_path="imported/",
            source_prefix="data/",
            commit_message="Import data from S3",
        )
        assert job_id == "job-abc-123"
        assert route.called

    def test_from_repository(self, mock_api, repo):
        """POST .../import with source_organization + source_repository returns job_id."""
        route = mock_api.post("/organizations/test-org/repositories/test-repo/import").mock(
            return_value=httpx.Response(202, json={"job_id": "job-cross-1"})
        )
        job_id = repo.imports.from_repository(
            "other-org/other-repo",
            destination_path="cross-imported/",
            commit_message="Cross-repo import",
        )
        assert job_id == "job-cross-1"
        assert route.called

    def test_from_repository_invalid_path(self, repo):
        """Invalid repo_path raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="expected 'org/repo' format"):
            repo.imports.from_repository("bad-path", destination_path="dest/")

    def test_status(self, mock_api, repo):
        """GET .../import/{job_id} returns ImportJob with connector fields."""
        mock_api.get("/organizations/test-org/repositories/test-repo/import/job-abc-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "job-abc-123",
                    "repository_id": "repo-1",
                    "connector_id": "conn-1",
                    "source_prefix": "data/",
                    "destination_path": "imported/",
                    "commit_message": "Import data from S3",
                    "status": "completed",
                    "objects_imported": 150,
                    "commit_id": "import-commit-id",
                    "error": "",
                    "created_by": "user-1",
                    "created_at": "2025-06-15T10:00:00Z",
                    "updated_at": "2025-06-15T10:05:00Z",
                },
            )
        )
        job = repo.imports.status("job-abc-123")
        assert isinstance(job, ImportJob)
        assert job.id == "job-abc-123"
        assert job.status == "completed"
        assert job.objects_imported == 150
        assert job.commit_id == "import-commit-id"
        assert job.source_prefix == "data/"

    def test_status_cross_repo(self, mock_api, repo):
        """GET .../import/{job_id} returns ImportJob with cross-repo fields."""
        mock_api.get("/organizations/test-org/repositories/test-repo/import/job-cross-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "job-cross-1",
                    "repository_id": "repo-1",
                    "source_repository_id": "src-repo-id",
                    "source_organization": "other-org",
                    "source_repository": "other-repo",
                    "destination_path": "cross-imported/",
                    "commit_message": "Cross-repo import",
                    "status": "in_progress",
                    "objects_imported": 42,
                    "created_at": "2025-06-15T12:00:00Z",
                },
            )
        )
        job = repo.imports.status("job-cross-1")
        assert isinstance(job, ImportJob)
        assert job.id == "job-cross-1"
        assert job.source_repository_id == "src-repo-id"
        assert job.source_organization == "other-org"
        assert job.source_repository == "other-repo"
        assert job.connector_id == ""
