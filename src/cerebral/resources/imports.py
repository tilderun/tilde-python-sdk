"""Import resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerebral.models import ImportJob

if TYPE_CHECKING:
    from cerebral.client import Client


class ImportResource:
    """Import operations on a repository."""

    def __init__(self, client: Client, org: str, repo: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo

    @property
    def _repo_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}"

    def start(
        self,
        connector_id: str,
        source_path: str,
        destination_path: str,
        *,
        use_versioning: bool = False,
        commit_message: str | None = None,
    ) -> str:
        """Start an import job.

        Returns:
            The job ID.
        """
        body: dict[str, Any] = {
            "connector_id": connector_id,
            "source_path": source_path,
            "destination_path": destination_path,
            "use_versioning": use_versioning,
        }
        if commit_message is not None:
            body["commit_message"] = commit_message
        data = self._client._post_json(
            f"{self._repo_path}/import",
            json=body,
        )
        return str(data.get("job_id", ""))

    def status(self, job_id: str) -> ImportJob:
        """Get import job status."""
        data = self._client._get_json(f"{self._repo_path}/import/{job_id}")
        return ImportJob.from_dict(data)
