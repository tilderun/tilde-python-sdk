"""Session resource for transactional object operations."""

from __future__ import annotations

import time
import warnings
from typing import TYPE_CHECKING, Any

from cerebral._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from cerebral.exceptions import NotFoundError
from cerebral.models import CommitResult, EntryRecord

if TYPE_CHECKING:
    from cerebral.client import Client
    from cerebral.resources.objects import SessionObjectCollection

_APPROVAL_POLL_INTERVAL = 2  # seconds


class Session:
    """A transactional editing session on a repository.

    Sessions act like transactions: stage object writes and deletes, then
    either commit or rollback.  When used as a context manager, the session
    rolls back automatically on exception and on clean exit if ``commit()``
    was not called::

        with repo.session() as session:
            session.objects.put('data/report.csv', b'content')
            session.commit('update CSV files')

    For manual control::

        session = repo.session()
        session.objects.put('data/file.csv', b'content')
        session.commit('my changes')  # or session.rollback()
    """

    def __init__(
        self,
        client: Client,
        org: str,
        repo: str,
        session_id: str,
    ) -> None:
        self._client = client
        self._org = org
        self._repo = repo
        self._session_id = session_id
        self._committed = False
        self._rolled_back = False

    @property
    def session_id(self) -> str:
        """The server-assigned session ID."""
        return self._session_id

    @property
    def _repo_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}"

    @property
    def objects(self) -> SessionObjectCollection:
        """Object access within this session (read and write)."""
        from cerebral.resources.objects import SessionObjectCollection

        return SessionObjectCollection(
            self._client, self._org, self._repo, self._session_id
        )

    def uncommitted(
        self,
        *,
        prefix: str | None = None,
        after: str | None = None,
        amount: int | None = None,
    ) -> PaginatedIterator[EntryRecord]:
        """List uncommitted changes in this session."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[EntryRecord]:
            params: dict[str, str | int] = {"session_id": self._session_id}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            if prefix is not None:
                params["prefix"] = prefix
            if amount is not None:
                params["amount"] = amount
            else:
                params["amount"] = DEFAULT_PAGE_SIZE
            data = self._client._get_json(f"{self._repo_path}/changes", params=params)
            items = [EntryRecord.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    def commit(
        self,
        message: str,
        *,
        metadata: dict[str, str] | None = None,
        block_for_approval: bool = True,
    ) -> str | None:
        """Commit this session (apply all staged changes).

        If the repository requires approval for agent commits, the server
        responds with *202 Accepted*.  In that case a :class:`UserWarning` is
        emitted containing the web URL where a human can review and approve
        the changes.

        By default the call blocks, polling every 2 seconds until the session
        is approved (or rolled back).  Pass ``block=False`` to return
        immediately after the warning is emitted.

        Args:
            message: Commit message describing the changes.
            metadata: Optional key-value metadata to attach to the commit.
            block_for_approval: When approval is required, wait for it (default ``True``).

        Returns:
            The new commit ID, ``""`` when approval was required and
            *block_for_approval* is ``True``, or ``None`` when approval was
            required and *block_for_approval* is ``False``.
        """
        body: dict[str, Any] = {"message": message}
        if metadata:
            body["metadata"] = metadata
        response = self._client._post(
            f"{self._repo_path}/sessions/{self._session_id}",
            json=body,
        )
        if response.status_code == 202:
            data = response.json()
            web_url = data.get("web_url", "")
            warnings.warn(
                f"Approval required – review and approve at: {web_url}",
                stacklevel=2,
            )
            self._committed = True
            if block_for_approval:
                self._poll_approval()
                return ""
            return None
        data = response.json()
        self._committed = True
        return str(data.get("commit_id", ""))

    def commit_result(
        self,
        message: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> CommitResult:
        """Commit and return a structured :class:`~cerebral.models.CommitResult`.

        Unlike :meth:`commit`, this method never blocks for approval and does
        not emit warnings — it simply returns the result envelope.
        """
        body: dict[str, Any] = {"message": message}
        if metadata:
            body["metadata"] = metadata
        response = self._client._post(
            f"{self._repo_path}/sessions/{self._session_id}",
            json=body,
        )
        self._committed = True
        if response.status_code == 202:
            data = response.json()
            return CommitResult(
                status="approval_required",
                web_url=data.get("web_url", ""),
            )
        data = response.json()
        return CommitResult(
            status="committed",
            commit_id=str(data.get("commit_id", "")),
        )

    def _poll_approval(self) -> None:
        """Block until the approval endpoint returns 404 (committed/rolled back)."""
        approval_path = f"{self._repo_path}/sessions/{self._session_id}/approve"
        while True:
            time.sleep(_APPROVAL_POLL_INTERVAL)
            try:
                self._client._head(approval_path)
            except NotFoundError:
                return

    def rollback(self) -> None:
        """Rollback this session (discard all staged changes)."""
        self._client._delete(
            f"{self._repo_path}/sessions/{self._session_id}",
        )
        self._rolled_back = True

    def __enter__(self) -> Session:
        return self

    def __exit__(self, exc_type: type | None, exc_val: object, exc_tb: object) -> None:
        if self._committed or self._rolled_back:
            return
        self.rollback()
