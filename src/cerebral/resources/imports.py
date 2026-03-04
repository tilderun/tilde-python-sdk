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

    def from_connector(
        self,
        connector_id: str,
        destination_path: str,
        *,
        source_prefix: str | None = None,
        commit_message: str | None = None,
    ) -> str:
        """Start an import from an external connector (S3, GCS, etc.).

        Returns:
            The job ID.
        """
        body: dict[str, Any] = {
            "connector_id": connector_id,
            "destination_path": destination_path,
        }
        if source_prefix is not None:
            body["source_prefix"] = source_prefix
        if commit_message is not None:
            body["commit_message"] = commit_message
        data = self._client._post_json(
            f"{self._repo_path}/import",
            json=body,
        )
        return str(data.get("job_id", ""))

    def from_repository(
        self,
        repo_path: str,
        destination_path: str,
        *,
        source_prefix: str | None = None,
        commit_message: str | None = None,
    ) -> str:
        """Start a cross-repository import.

        Args:
            repo_path: Source repository path in ``"org/repo"`` format.
            destination_path: Destination path in this repository.
            source_prefix: Optional prefix filter in the source repository.
            commit_message: Optional commit message for the import.

        Returns:
            The job ID.
        """
        parts = repo_path.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid repository path {repo_path!r}: expected 'org/repo' format")
        body: dict[str, Any] = {
            "source_organization": parts[0],
            "source_repository": parts[1],
            "destination_path": destination_path,
        }
        if source_prefix is not None:
            body["source_prefix"] = source_prefix
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
