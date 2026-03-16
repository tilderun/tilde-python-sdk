"""Stream wrapper for sandbox command stdout/stderr output."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tilde.client import Client

_DEFAULT_CHUNK_SIZE = 8192


class OutputStream:
    """Stream interface for command stdout/stderr output.

    Provides multiple ways to consume output data::

        result = repo.execute("echo hello")

        # Read all as bytes
        data = result.stdout.read()

        # Read all as text
        text = result.stdout.text()

        # Iterate over byte chunks
        for chunk in result.stdout.iter_bytes(4096):
            process(chunk)

        # Iterate over text chunks
        for chunk in result.stdout.iter_text(4096):
            process(chunk)

        # Iterate over lines
        for line in result.stdout.iter_lines():
            print(line)

    When constructed with a client and path (lazy mode), data is fetched
    from the HTTP endpoint on first access and cached.
    """

    def __init__(
        self,
        data: bytes | None = None,
        *,
        _client: Client | None = None,
        _path: str | None = None,
    ) -> None:
        self._data = data
        self._client = _client
        self._path = _path

    def _ensure_data(self) -> bytes:
        if self._data is None:
            if self._client is not None and self._path is not None:
                with self._client._stream("GET", self._path) as resp:
                    self._data = resp.read()
            else:
                self._data = b""
        return self._data

    def read(self) -> bytes:
        """Read the entire output as bytes."""
        return self._ensure_data()

    def text(self, encoding: str = "utf-8") -> str:
        """Read the entire output as a decoded string.

        Args:
            encoding: Character encoding (default ``"utf-8"``).
        """
        return self._ensure_data().decode(encoding)

    def iter_bytes(self, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> Iterator[bytes]:
        """Yield output in byte chunks.

        Args:
            chunk_size: Maximum number of bytes per chunk.
        """
        data = self._ensure_data()
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    def iter_text(self, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> Iterator[str]:
        """Yield output in text chunks.

        Args:
            chunk_size: Maximum number of characters per chunk.
        """
        text = self.text()
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]

    def iter_lines(self) -> Iterator[str]:
        """Yield output line by line (without trailing newlines)."""
        text = self.text()
        if text:
            yield from text.splitlines()

    def __repr__(self) -> str:
        if self._data is not None:
            return f"OutputStream({len(self._data)} bytes)"
        return "OutputStream(pending)"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OutputStream):
            return self._ensure_data() == other._ensure_data()
        return NotImplemented

    def __str__(self) -> str:
        return self.text()
