"""Repository resource with lazy-loaded properties."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerebral._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from cerebral.models import CommitData, RepositoryData, _parse_dt

if TYPE_CHECKING:
    from datetime import datetime

    from cerebral.client import Client
    from cerebral.resources.connectors import RepoConnectorCollection
    from cerebral.resources.imports import ImportResource
    from cerebral.resources.sessions import Session


class OrgRepositoryCollection:
    """Repository operations within an organization."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    def create(
        self,
        name: str,
        *,
        description: str = "",
        visibility: str = "private",
    ) -> RepositoryData:
        """Create a repository.

        Args:
            name: Repository name.
            description: Optional description.
            visibility: ``"private"`` (default) or ``"public"``.
        """
        body: dict[str, str] = {"name": name, "visibility": visibility}
        if description:
            body["description"] = description
        data = self._client._post_json(
            f"/organizations/{self._org}/repositories", json=body
        )
        return RepositoryData.from_dict(data)

    def list(self, *, after: str | None = None) -> PaginatedIterator[RepositoryData]:
        """List repositories in the organization."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[RepositoryData]:
            params: dict[str, str | int] = {"amount": DEFAULT_PAGE_SIZE}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            data = self._client._get_json(f"/organizations/{self._org}/repositories", params=params)
            items = [RepositoryData.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)


class Repository:
    """A Cerebral repository.  Properties are lazy-loaded on first access."""

    def __init__(self, client: Client, org: str, name: str) -> None:
        self._client = client
        self._org = org
        self._name = name
        self._loaded = False
        self._raw: dict[str, Any] = {}

    @property
    def _repo_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._name}"

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._raw = self._client._get_json(self._repo_path)
        self._loaded = True

    # -- Lazy-loaded properties -----------------------------------------------

    @property
    def id(self) -> str:
        self._ensure_loaded()
        return str(self._raw.get("id", ""))

    @property
    def description(self) -> str:
        self._ensure_loaded()
        return str(self._raw.get("description", ""))

    @property
    def visibility(self) -> str:
        self._ensure_loaded()
        return str(self._raw.get("visibility", ""))

    @property
    def created_by(self) -> str:
        self._ensure_loaded()
        return str(self._raw.get("created_by", ""))

    @property
    def created_at(self) -> datetime | None:
        self._ensure_loaded()
        return _parse_dt(self._raw.get("created_at"))

    # -- Sessions -------------------------------------------------------------

    def session(self) -> Session:
        """Create a new editing session.

        Can be used as a context manager for automatic rollback on error::

            with repo.session() as session:
                session.objects.put('data/report.csv', b'content')
                session.commit('update CSV files')

        Or used explicitly::

            session = repo.session()
            session.objects.put('data/file.csv', b'content')
            session.commit('my changes')

        Returns:
            A :class:`~cerebral.resources.sessions.Session`.
        """
        from cerebral.resources.sessions import Session

        data = self._client._post_json(f"{self._repo_path}/sessions")
        session_id = data["session_id"]
        return Session(self._client, self._org, self._name, session_id)

    def attach(self, session_id: str) -> Session:
        """Attach to an existing session by ID.

        Useful for resuming a session from another thread, process, or machine::

            session = repo.attach(session_id)
            session.objects.put('data/file.csv', b'content')
            session.commit('my changes')

        Args:
            session_id: The session ID to attach to.

        Returns:
            A :class:`~cerebral.resources.sessions.Session`.
        """
        from cerebral.resources.sessions import Session

        return Session(self._client, self._org, self._name, session_id)

    # -- Timeline (commit log) ------------------------------------------------

    def timeline(
        self,
        *,
        ref: str | None = None,
        after: str | None = None,
        amount: int | None = None,
    ) -> PaginatedIterator[CommitData]:
        """List commits in the repository (newest first).

        Args:
            ref: Branch name, tag name, or commit ID. Defaults to the
                repository's default branch.
            after: Pagination cursor.
            amount: Page size (default 100).

        Returns:
            An auto-paginating iterator of :class:`~cerebral.models.CommitData`.
        """
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[CommitData]:
            params: dict[str, str | int] = {}
            if ref is not None:
                params["ref"] = ref
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            if amount is not None:
                params["amount"] = amount
            else:
                params["amount"] = DEFAULT_PAGE_SIZE
            data = self._client._get_json(f"{self._repo_path}/log", params=params)
            items = [CommitData.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    # -- Sub-resources --------------------------------------------------------

    @property
    def connectors(self) -> RepoConnectorCollection:
        from cerebral.resources.connectors import RepoConnectorCollection

        return RepoConnectorCollection(self._client, self._org, self._name)

    @property
    def imports(self) -> ImportResource:
        from cerebral.resources.imports import ImportResource

        return ImportResource(self._client, self._org, self._name)

    # -- Mutations ------------------------------------------------------------

    def update(
        self,
        *,
        description: str | None = None,
        visibility: str | None = None,
    ) -> RepositoryData:
        """Update repository description or visibility."""
        body: dict[str, str] = {}
        if description is not None:
            body["description"] = description
        if visibility is not None:
            body["visibility"] = visibility
        data = self._client._put_json(self._repo_path, json=body)
        self._raw = data
        self._loaded = True
        return RepositoryData.from_dict(data)

    def delete(self) -> None:
        """Delete this repository (soft delete)."""
        self._client._delete(self._repo_path)
