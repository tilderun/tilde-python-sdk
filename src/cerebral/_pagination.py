"""Offset-based pagination iterator for the Cerebral API."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 100


@dataclass
class PageResult(Generic[T]):
    """One page of results returned by a paginated endpoint."""

    items: list[T]
    has_more: bool
    next_offset: str | None
    max_per_page: int | None = None


class PaginatedIterator(Iterator[T]):
    """Lazily fetches pages from the API, yielding items one at a time.

    Uses the server's offset-based pagination: passes ``after=next_offset``
    for each subsequent page.
    """

    def __init__(self, fetch_page: Callable[[str | None], PageResult[T]]) -> None:
        self._fetch_page = fetch_page
        self._buffer: list[T] = []
        self._next_offset: str | None = None
        self._exhausted = False
        self._first_request = True

    def __iter__(self) -> PaginatedIterator[T]:
        return self

    def __next__(self) -> T:
        if self._buffer:
            return self._buffer.pop(0)
        if self._exhausted:
            raise StopIteration
        page = self._fetch_page(self._next_offset)
        self._first_request = False
        self._buffer = page.items
        self._next_offset = page.next_offset
        if not page.has_more:
            self._exhausted = True
        if not self._buffer:
            raise StopIteration
        return self._buffer.pop(0)
