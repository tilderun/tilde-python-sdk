"""Object collections for reading and writing objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

import httpx

from cerebral._object_reader import ObjectReader
from cerebral._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from cerebral.exceptions import TransportError
from cerebral.models import ListingEntry, ObjectMetadata, PutObjectResult

if TYPE_CHECKING:
    import builtins
    from collections.abc import Iterable

    from cerebral.client import Client


class ReadOnlyObjectCollection:
    """Object access scoped to a committed snapshot (no session)."""

    def __init__(self, client: Client, org: str, repo: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo

    @property
    def _repo_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}"

    def list(
        self,
        *,
        prefix: str | None = None,
        delimiter: str | None = None,
        after: str | None = None,
        amount: int | None = None,
    ) -> PaginatedIterator[ListingEntry]:
        """List objects, auto-paginating.

        Args:
            prefix: Filter by key prefix.
            delimiter: Directory grouping delimiter (e.g. ``"/"``).
            after: Starting offset for the first page.
            amount: Page size (default 100).
        """
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[ListingEntry]:
            params: dict[str, str | int] = {}
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
            data = self._client._get_json(f"{self._repo_path}/objects", params=params)
            items = [ListingEntry.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    def get(self, path: str, *, cache: bool = True, presign: bool = True) -> ObjectReader:
        """Get an object's content as a streaming reader.

        Args:
            path: Object path.
            cache: Cache content in memory after first read (default ``True``).
                For large objects, use ``cache=False`` and ``.iter_bytes()``.
            presign: Use presigned URL for download (default ``True``).

        Returns:
            An :class:`~cerebral._object_reader.ObjectReader`.
        """
        return ObjectReader(
            self._client,
            f"{self._repo_path}/object",
            {"path": path},
            cache=cache,
            presign=presign,
        )

    def head(self, path: str) -> ObjectMetadata:
        """Check object existence and retrieve metadata from headers.

        Returns:
            An :class:`~cerebral.models.ObjectMetadata` with etag,
            content_type, content_length, and reproducible fields.
        """
        response = self._client._head(
            f"{self._repo_path}/object",
            params={"path": path},
        )
        repro_header = response.headers.get("x-cerebral-reproducible")
        reproducible: bool | None = None
        if repro_header == "true":
            reproducible = True
        elif repro_header == "false":
            reproducible = False
        cl = response.headers.get("content-length")
        return ObjectMetadata(
            etag=response.headers.get("etag"),
            content_type=response.headers.get("content-type"),
            content_length=int(cl) if cl else None,
            reproducible=reproducible,
        )


class SessionObjectCollection:
    """Object access within a session — supports read and write operations."""

    def __init__(self, client: Client, org: str, repo: str, session_id: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo
        self._session_id = session_id

    @property
    def _repo_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}"

    def list(
        self,
        *,
        prefix: str | None = None,
        delimiter: str | None = None,
        after: str | None = None,
        amount: int | None = None,
    ) -> PaginatedIterator[ListingEntry]:
        """List objects in this session, auto-paginating."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[ListingEntry]:
            params: dict[str, str | int] = {"session_id": self._session_id}
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
            data = self._client._get_json(f"{self._repo_path}/objects", params=params)
            items = [ListingEntry.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    def get(self, path: str, *, cache: bool = True, presign: bool = True) -> ObjectReader:
        """Get an object's content as a streaming reader."""
        return ObjectReader(
            self._client,
            f"{self._repo_path}/object",
            {"session_id": self._session_id, "path": path},
            cache=cache,
            presign=presign,
        )

    def head(self, path: str) -> ObjectMetadata:
        """Check object existence and retrieve metadata from headers."""
        response = self._client._head(
            f"{self._repo_path}/object",
            params={"session_id": self._session_id, "path": path},
        )
        repro_header = response.headers.get("x-cerebral-reproducible")
        reproducible: bool | None = None
        if repro_header == "true":
            reproducible = True
        elif repro_header == "false":
            reproducible = False
        cl = response.headers.get("content-length")
        return ObjectMetadata(
            etag=response.headers.get("etag"),
            content_type=response.headers.get("content-type"),
            content_length=int(cl) if cl else None,
            reproducible=reproducible,
        )

    def put(
        self,
        path: str,
        data: bytes | bytearray | memoryview | BinaryIO | Iterable[bytes],
    ) -> PutObjectResult:
        """Upload an object into this session via presigned URL.

        Uses a three-step flow: stage (get presigned URL), upload to the
        presigned URL, then finalize to record the object in the catalog.

        Args:
            path: Object path.
            data: Content as bytes, file-like, or iterable of bytes chunks.
        """
        # 1. Stage: obtain a presigned upload URL
        stage = self._client._post_json(
            f"{self._repo_path}/object/stage",
            params={"session_id": self._session_id, "path": path},
        )
        upload_url: str = stage["upload_url"]
        physical_address: str = stage["physical_address"]
        signature: str = stage["signature"]
        expires_at: str = stage["expires_at"]

        # 2. Upload directly to the presigned URL
        if isinstance(data, (bytes, bytearray, memoryview)):
            content: bytes | BinaryIO | Iterable[bytes] = bytes(data)
        else:
            content = data

        try:
            upload_resp = self._client._http.put(
                upload_url,
                content=content,
                headers={"Content-Type": "application/octet-stream"},
            )
        except httpx.TransportError as exc:
            raise TransportError(f"Upload to presigned URL failed: {exc}", cause=exc) from exc
        if not upload_resp.is_success:
            raise TransportError(
                f"Upload to presigned URL failed with status {upload_resp.status_code}"
            )

        # 3. Finalize: record the object in the catalog
        finalize = self._client._put_json(
            f"{self._repo_path}/object/finalize",
            params={
                "session_id": self._session_id,
                "path": path,
                "expires_at": expires_at,
            },
            json={
                "physical_address": physical_address,
                "signature": signature,
                "content_type": "application/octet-stream",
            },
        )
        return PutObjectResult.from_dict(finalize)

    def delete(self, path: str) -> None:
        """Delete an object (stage tombstone in this session)."""
        self._client._delete(
            f"{self._repo_path}/object",
            params={"session_id": self._session_id, "path": path},
        )

    def delete_many(self, paths: builtins.list[str]) -> int:
        """Delete multiple objects in a single request.

        Args:
            paths: List of object paths to delete.

        Returns:
            The number of objects deleted.
        """
        data = self._client._post_json(
            f"{self._repo_path}/objects/delete",
            params={"session_id": self._session_id},
            json={"paths": paths},
        )
        count: int = data.get("deleted", 0)
        return count
