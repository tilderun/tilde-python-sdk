"""Tests for ImportResource."""

import httpx

from cerebral.models import ImportJob


class TestImportResource:
    def test_start(self, mock_api, repo):
        """POST .../import returns job_id."""
        route = mock_api.post("/organizations/test-org/repositories/test-repo/import").mock(
            return_value=httpx.Response(202, json={"job_id": "job-abc-123"})
        )
        job_id = repo.imports.start(
            connector_id="conn-1",
            source_path="s3://bucket/data/",
            destination_path="imported/",
            commit_message="Import data from S3",
        )
        assert job_id == "job-abc-123"
        assert route.called

    def test_status(self, mock_api, repo):
        """GET .../import/{job_id} returns ImportJob."""
        mock_api.get("/organizations/test-org/repositories/test-repo/import/job-abc-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "job-abc-123",
                    "repository_id": "repo-1",
                    "connector_id": "conn-1",
                    "source_path": "s3://bucket/data/",
                    "destination_path": "imported/",
                    "use_versioning": False,
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
