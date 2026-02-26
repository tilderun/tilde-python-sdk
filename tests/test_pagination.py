import pytest

from cerebral._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator


class TestDefaultPageSize:
    def test_default_page_size_is_100(self):
        assert DEFAULT_PAGE_SIZE == 100


class TestEmptyResult:
    def test_empty_result_yields_nothing(self):
        def fetch(after):
            return PageResult(items=[], has_more=False, next_offset=None)

        it = PaginatedIterator(fetch)
        assert list(it) == []

    def test_empty_result_calls_fetch_once_with_none(self):
        calls = []

        def fetch(after):
            calls.append(after)
            return PageResult(items=[], has_more=False, next_offset=None)

        it = PaginatedIterator(fetch)
        list(it)
        assert calls == [None]


class TestSinglePage:
    def test_single_page_returns_all_items(self):
        def fetch(after):
            return PageResult(items=[1, 2, 3], has_more=False, next_offset=None)

        it = PaginatedIterator(fetch)
        assert list(it) == [1, 2, 3]

    def test_single_page_calls_fetch_once(self):
        calls = []

        def fetch(after):
            calls.append(after)
            return PageResult(items=["a", "b"], has_more=False, next_offset=None)

        it = PaginatedIterator(fetch)
        list(it)
        assert calls == [None]

    def test_single_page_items_yielded_one_at_a_time(self):
        yielded = []

        def fetch(after):
            return PageResult(items=[10, 20, 30], has_more=False, next_offset=None)

        it = PaginatedIterator(fetch)
        for item in it:
            yielded.append(item)
        assert yielded == [10, 20, 30]


class TestMultiPage:
    def test_two_pages(self):
        def fetch(after):
            if after is None:
                return PageResult(
                    items=[1, 2],
                    has_more=True,
                    next_offset="page2",
                )
            elif after == "page2":
                return PageResult(
                    items=[3, 4],
                    has_more=False,
                    next_offset=None,
                )
            else:
                raise AssertionError(f"Unexpected offset: {after}")

        it = PaginatedIterator(fetch)
        assert list(it) == [1, 2, 3, 4]

    def test_three_pages(self):
        def fetch(after):
            if after is None:
                return PageResult(
                    items=["a"],
                    has_more=True,
                    next_offset="offset_b",
                )
            elif after == "offset_b":
                return PageResult(
                    items=["b"],
                    has_more=True,
                    next_offset="offset_c",
                )
            elif after == "offset_c":
                return PageResult(
                    items=["c"],
                    has_more=False,
                    next_offset=None,
                )
            else:
                raise AssertionError(f"Unexpected offset: {after}")

        it = PaginatedIterator(fetch)
        assert list(it) == ["a", "b", "c"]

    def test_fetch_called_with_none_then_offsets(self):
        calls = []

        def fetch(after):
            calls.append(after)
            if after is None:
                return PageResult(
                    items=[1],
                    has_more=True,
                    next_offset="page2",
                )
            elif after == "page2":
                return PageResult(
                    items=[2],
                    has_more=True,
                    next_offset="page3",
                )
            elif after == "page3":
                return PageResult(
                    items=[3],
                    has_more=False,
                    next_offset=None,
                )
            else:
                raise AssertionError(f"Unexpected offset: {after}")

        it = PaginatedIterator(fetch)
        list(it)
        assert calls == [None, "page2", "page3"]


class TestIterationStops:
    def test_stops_when_has_more_is_false(self):
        call_count = 0

        def fetch(after):
            nonlocal call_count
            call_count += 1
            if call_count > 5:
                raise AssertionError("fetch_page called too many times")
            if after is None:
                return PageResult(
                    items=[1],
                    has_more=True,
                    next_offset="next",
                )
            else:
                return PageResult(
                    items=[2],
                    has_more=False,
                    next_offset=None,
                )

        it = PaginatedIterator(fetch)
        result = list(it)
        assert result == [1, 2]
        assert call_count == 2

    def test_does_not_fetch_beyond_last_page(self):
        """When has_more is False, no further fetch calls should be made."""
        fetch_count = 0

        def fetch(after):
            nonlocal fetch_count
            fetch_count += 1
            return PageResult(items=[42], has_more=False, next_offset=None)

        it = PaginatedIterator(fetch)
        list(it)
        assert fetch_count == 1


class TestItemsYieldedOneAtATime:
    def test_iterator_protocol(self):
        def fetch(after):
            if after is None:
                return PageResult(
                    items=[1, 2, 3],
                    has_more=True,
                    next_offset="p2",
                )
            else:
                return PageResult(
                    items=[4, 5],
                    has_more=False,
                    next_offset=None,
                )

        it = PaginatedIterator(fetch)
        iterator = iter(it)
        assert next(iterator) == 1
        assert next(iterator) == 2
        assert next(iterator) == 3
        assert next(iterator) == 4
        assert next(iterator) == 5
        with pytest.raises(StopIteration):
            next(iterator)

    def test_partial_consumption(self):
        """Consuming only some items should not fetch all pages."""
        calls = []

        def fetch(after):
            calls.append(after)
            if after is None:
                return PageResult(
                    items=[1, 2, 3],
                    has_more=True,
                    next_offset="p2",
                )
            else:
                return PageResult(
                    items=[4, 5, 6],
                    has_more=False,
                    next_offset=None,
                )

        it = PaginatedIterator(fetch)
        iterator = iter(it)
        first = next(iterator)
        assert first == 1
        # Only the first page should have been fetched so far
        assert calls == [None]


class TestPageResultFields:
    def test_max_per_page_field(self):
        page = PageResult(
            items=[1, 2],
            has_more=False,
            next_offset=None,
            max_per_page=50,
        )
        assert page.max_per_page == 50
        assert page.items == [1, 2]
        assert page.has_more is False
        assert page.next_offset is None

    def test_page_result_with_typed_items(self):
        page: PageResult[str] = PageResult(
            items=["hello", "world"],
            has_more=True,
            next_offset="abc",
        )
        assert page.items == ["hello", "world"]
        assert page.has_more is True
        assert page.next_offset == "abc"
