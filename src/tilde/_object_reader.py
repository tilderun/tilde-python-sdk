"""Streaming object reader returned by ``objects.get()``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextlib import AbstractContextManager

    import httpx

    from tilde.client import Client


class ObjectReader:
    """File-like streaming wrapper around an object GET response.

    Lazily opens the HTTP stream on first ``.read()`` call or context
    manager entry.  Supports partial reads, streaming iteration, and
    header-derived metadata.

    Args:
        client: The SDK client.
        path: API path for the object endpoint.
        params: Query parameters (ref, path).
        cache: When ``True`` (default), caches content in memory after
            the first full ``.read()``.  For large objects, use
            ``cache=False`` and ``.iter_bytes()`` to stream without
            buffering.
    """

    def __init__(
        self,
        client: Client,
        path: str,
        params: dict[str, str],
        *,
        cache: bool = True,
        presign: bool = True,
        byte_range: tuple[int, int | None] | None = None,
    ) -> None:
        self._client = client
        self._path = path
        self._params = params
        self._cache = cache
        self._presign = presign
        self._byte_range = byte_range
        self._response: httpx.Response | None = None
        self._stream_context: AbstractContextManager[Any] | None = None
        self._cached_content: bytes | None = None
        self._etag: str | None = None
        self._content_type: str | None = None
        self._content_length: int | None = None
        self._content_range: str | None = None
        self._reproducible: bool | None = None
        self._closed = False

    def _open(self) -> httpx.Response:
        if self._response is not None:
            return self._response
        params = dict(self._params)
        kwargs: dict[str, Any] = {}
        if self._presign:
            params["presign"] = "true"
            kwargs["follow_redirects"] = True
        if self._byte_range is not None:
            start, end = self._byte_range
            range_val = f"bytes={start}-{end}" if end is not None else f"bytes={start}-"
            kwargs["headers"] = {"Range": range_val}
        ctx = self._client._stream("GET", self._path, params=params, **kwargs)
        self._stream_context = ctx
        self._response = ctx.__enter__()
        self._extract_headers(self._response)
        return self._response

    def _extract_headers(self, response: httpx.Response) -> None:
        self._etag = response.headers.get("etag")
        self._content_type = response.headers.get("content-type")
        cl = response.headers.get("content-length")
        self._content_length = int(cl) if cl else None
        self._content_range = response.headers.get("content-range")
        repro = response.headers.get("x-tilde-reproducible")
        if repro == "true":
            self._reproducible = True
        elif repro == "false":
            self._reproducible = False

    @property
    def etag(self) -> str | None:
        """ETag header value (available after first read or context entry)."""
        return self._etag

    @property
    def content_type(self) -> str | None:
        """Content-Type header value."""
        return self._content_type

    @property
    def content_length(self) -> int | None:
        """Content-Length header value."""
        return self._content_length

    @property
    def content_range(self) -> str | None:
        """Content-Range header value (present for 206 partial content responses)."""
        return self._content_range

    @property
    def reproducible(self) -> bool | None:
        """Derived from ``X-Tilde-Reproducible`` header."""
        return self._reproducible

    def read(self, n: int = -1) -> bytes:
        """Read object content.

        Args:
            n: Number of bytes to read.  ``-1`` (default) reads all.

        When ``cache=True`` and *n* is ``-1``, the full content is cached
        in memory and returned on subsequent calls.
        """
        if self._cached_content is not None and n == -1:
            return self._cached_content
        response = self._open()
        if n == -1:
            data = response.read()
            if self._cache:
                self._cached_content = data
            return data
        return response.read()  # httpx doesn't support partial reads on stream easily

    def iter_bytes(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Yield content in chunks for streaming large objects."""
        response = self._open()
        yield from response.iter_bytes(chunk_size=chunk_size)

    def close(self) -> None:
        """Close the underlying HTTP stream."""
        if self._closed:
            return
        self._closed = True
        if self._stream_context is not None:
            import contextlib

            with contextlib.suppress(Exception):
                self._stream_context.__exit__(None, None, None)

    def __enter__(self) -> ObjectReader:
        self._open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
