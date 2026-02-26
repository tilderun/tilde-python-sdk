"""Commit resource with diff support."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerebral._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from cerebral.models import ListingEntry, _parse_dt

if TYPE_CHECKING:
    from datetime import datetime

    from cerebral.client import Client
    from cerebral.resources.objects import ReadOnlyObjectCollection


class Commit:
    """A commit in the repository timeline.

    Provides lazy-loaded commit properties and a ``diff()`` method to
    inspect what changed in this commit.
    """

    def __init__(self, client: Client, org: str, repo: str, commit_id: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo
        self._id = commit_id
        self._loaded = False
        self._raw: dict[str, Any] = {}
        self._committer: str = ""
        self._message: str = ""
        self._creation_date: datetime | None = None
        self._parents: list[str] = []
        self._metadata: dict[str, str] = {}
        self._meta_range_id: str = ""
        self._object_count: int | None = None
        self._total_size: int | None = None

    @property
    def _repo_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}"

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        data = self._client._get_json(f"{self._repo_path}/commits/{self._id}")
        self._populate(data)
        self._loaded = True

    def _populate(self, data: dict[str, Any]) -> None:
        self._raw = data
        self._id = data.get("id", self._id)
        self._committer = data.get("committer", "")
        self._message = data.get("message", "")
        self._creation_date = _parse_dt(data.get("creation_date"))
        self._parents = data.get("parents", [])
        self._metadata = data.get("metadata", {})
        self._meta_range_id = data.get("meta_range_id", "")
        self._object_count = data.get("object_count")
        self._total_size = data.get("total_size")

    @property
    def id(self) -> str:
        return self._id

    @property
    def committer(self) -> str:
        self._ensure_loaded()
        return self._committer

    @property
    def message(self) -> str:
        self._ensure_loaded()
        return self._message

    @property
    def creation_date(self) -> datetime | None:
        self._ensure_loaded()
        return self._creation_date

    @property
    def parents(self) -> list[str]:
        self._ensure_loaded()
        return self._parents

    @property
    def metadata(self) -> dict[str, str]:
        self._ensure_loaded()
        return self._metadata

    @property
    def meta_range_id(self) -> str:
        self._ensure_loaded()
        return self._meta_range_id

    @property
    def object_count(self) -> int | None:
        self._ensure_loaded()
        return self._object_count

    @property
    def total_size(self) -> int | None:
        self._ensure_loaded()
        return self._total_size

    @property
    def objects(self) -> ReadOnlyObjectCollection:
        """Read-only object access at this commit's snapshot."""
        from cerebral.resources.objects import ReadOnlyObjectCollection

        return ReadOnlyObjectCollection(self._client, self._org, self._repo)

    def diff(
        self,
        *,
        prefix: str | None = None,
        after: str | None = None,
        amount: int | None = None,
        delimiter: str | None = None,
    ) -> PaginatedIterator[ListingEntry]:
        """List changes introduced by this commit.

        Diffs this commit against its first parent. For the initial commit
        (no parents), diffs against an empty tree.

        Returns:
            An auto-paginating iterator of
            :class:`~cerebral.models.ListingEntry` with ``status`` indicating
            ``added``, ``modified``, or ``removed``.
        """
        self._ensure_loaded()
        left = self._parents[0] if self._parents else ""
        right = self._id
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[ListingEntry]:
            params: dict[str, str | int] = {"left": left, "right": right}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            if prefix is not None:
                params["prefix"] = prefix
            if delimiter is not None:
                params["delimiter"] = delimiter
            if amount is not None:
                params["amount"] = amount
            else:
                params["amount"] = DEFAULT_PAGE_SIZE
            data = self._client._get_json(f"{self._repo_path}/diff", params=params)
            items = [ListingEntry.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)
