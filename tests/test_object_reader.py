from contextlib import contextmanager
from unittest.mock import MagicMock

import httpx

from cerebral._object_reader import ObjectReader


def make_mock_client(content=b"hello", headers=None):
    """Create a mock client with a _stream context manager that yields a mock response."""
    if headers is None:
        headers = {}

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.headers = httpx.Headers(headers)
    mock_response.read.return_value = content
    mock_response.iter_bytes.return_value = iter([content])
    mock_response.close = MagicMock()

    @contextmanager
    def mock_stream(method, path, **kwargs):
        yield mock_response

    client = MagicMock()
    client._stream = mock_stream
    return client, mock_response


class TestRead:
    def test_read_returns_content(self):
        client, _ = make_mock_client(content=b"hello world")
        reader = ObjectReader(client, "/objects/foo", params={})
        assert reader.read() == b"hello world"

    def test_read_with_cache_returns_same_content_on_second_call(self):
        client, mock_response = make_mock_client(content=b"cached data")
        reader = ObjectReader(client, "/objects/foo", params={}, cache=True)

        first_read = reader.read()
        second_read = reader.read()

        assert first_read == b"cached data"
        assert second_read == b"cached data"
        # read() on the response should only be called once due to caching
        assert mock_response.read.call_count == 1

    def test_read_without_cache_does_not_cache(self):
        client, mock_response = make_mock_client(content=b"no cache")
        reader = ObjectReader(client, "/objects/foo", params={}, cache=False)

        first_read = reader.read()
        assert first_read == b"no cache"
        # With cache=False, _cached_content should remain None
        assert reader._cached_content is None
        # Response.read() is called each time since there's no cache
        second_read = reader.read()
        assert second_read == b"no cache"
        assert mock_response.read.call_count == 2


class TestIterBytes:
    def test_iter_bytes_yields_chunks(self):
        chunks = [b"chunk1", b"chunk2", b"chunk3"]

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = httpx.Headers({})
        mock_response.iter_bytes.return_value = iter(chunks)
        mock_response.close = MagicMock()

        @contextmanager
        def mock_stream(method, path, **kwargs):
            yield mock_response

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={})
        result = list(reader.iter_bytes(chunk_size=1024))
        assert result == [b"chunk1", b"chunk2", b"chunk3"]

    def test_iter_bytes_passes_chunk_size(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = httpx.Headers({})
        mock_response.iter_bytes.return_value = iter([b"data"])
        mock_response.close = MagicMock()

        @contextmanager
        def mock_stream(method, path, **kwargs):
            yield mock_response

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={})
        list(reader.iter_bytes(chunk_size=512))
        mock_response.iter_bytes.assert_called_with(chunk_size=512)


class TestHeaderExtraction:
    def test_etag_extracted_from_headers(self):
        client, _ = make_mock_client(
            content=b"data",
            headers={"etag": '"abc123"'},
        )
        reader = ObjectReader(client, "/objects/foo", params={})
        reader.read()
        assert reader.etag == '"abc123"'

    def test_content_type_extracted_from_headers(self):
        client, _ = make_mock_client(
            content=b"data",
            headers={"content-type": "application/json"},
        )
        reader = ObjectReader(client, "/objects/foo", params={})
        reader.read()
        assert reader.content_type == "application/json"

    def test_content_length_extracted_from_headers(self):
        client, _ = make_mock_client(
            content=b"data",
            headers={"content-length": "42"},
        )
        reader = ObjectReader(client, "/objects/foo", params={})
        reader.read()
        assert reader.content_length == 42

    def test_reproducible_extracted_from_headers(self):
        client, _ = make_mock_client(
            content=b"data",
            headers={"x-cerebral-reproducible": "true"},
        )
        reader = ObjectReader(client, "/objects/foo", params={})
        reader.read()
        assert reader.reproducible is True

    def test_missing_headers_return_none(self):
        client, _ = make_mock_client(content=b"data", headers={})
        reader = ObjectReader(client, "/objects/foo", params={})
        reader.read()
        assert reader.etag is None
        assert reader.content_type is None
        assert reader.content_length is None
        assert reader.reproducible is None


class TestContextManager:
    def test_context_manager_opens_stream(self):
        client, _mock_response = make_mock_client(content=b"ctx data")
        reader = ObjectReader(client, "/objects/foo", params={})

        with reader as r:
            assert r is reader
            data = r.read()
            assert data == b"ctx data"

    def test_context_manager_closes_on_exit(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = httpx.Headers({})
        mock_response.read.return_value = b"data"
        mock_response.close = MagicMock()

        stream_entered = False
        stream_exited = False

        @contextmanager
        def mock_stream(method, path, **kwargs):
            nonlocal stream_entered, stream_exited
            stream_entered = True
            yield mock_response
            stream_exited = True

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={})
        with reader:
            assert stream_entered is True
        # After exiting the context, close should have been triggered
        assert stream_exited is True


class TestClose:
    def test_close_is_idempotent(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = httpx.Headers({})
        mock_response.read.return_value = b"data"
        mock_response.close = MagicMock()

        @contextmanager
        def mock_stream(method, path, **kwargs):
            yield mock_response

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={})
        reader.read()

        # Calling close multiple times should not raise
        reader.close()
        reader.close()
        reader.close()

    def test_close_without_opening_does_not_raise(self):
        client, _ = make_mock_client()
        reader = ObjectReader(client, "/objects/foo", params={})
        # Closing without ever reading should not raise
        reader.close()


class TestPresign:
    def test_presign_true_adds_param_and_follow_redirects(self):
        """Default presign=True adds presign=true param and follow_redirects."""
        captured_kwargs = {}

        @contextmanager
        def mock_stream(method, path, **kwargs):
            captured_kwargs.update(kwargs)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.headers = httpx.Headers({})
            mock_response.read.return_value = b"data"
            mock_response.close = MagicMock()
            yield mock_response

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={"path": "bar"}, presign=True)
        reader.read()

        assert captured_kwargs["params"]["presign"] == "true"
        assert captured_kwargs["follow_redirects"] is True

    def test_presign_false_omits_param_and_follow_redirects(self):
        """presign=False does not add presign param or follow_redirects."""
        captured_kwargs = {}

        @contextmanager
        def mock_stream(method, path, **kwargs):
            captured_kwargs.update(kwargs)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.headers = httpx.Headers({})
            mock_response.read.return_value = b"data"
            mock_response.close = MagicMock()
            yield mock_response

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={"path": "bar"}, presign=False)
        reader.read()

        assert "presign" not in captured_kwargs["params"]
        assert "follow_redirects" not in captured_kwargs

    def test_presign_default_is_true(self):
        """presign defaults to True."""
        captured_kwargs = {}

        @contextmanager
        def mock_stream(method, path, **kwargs):
            captured_kwargs.update(kwargs)
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.headers = httpx.Headers({})
            mock_response.read.return_value = b"data"
            mock_response.close = MagicMock()
            yield mock_response

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={"path": "bar"})
        reader.read()

        assert captured_kwargs["params"]["presign"] == "true"
        assert captured_kwargs["follow_redirects"] is True


class TestLazyOpening:
    def test_stream_not_opened_until_read(self):
        stream_opened = False

        @contextmanager
        def mock_stream(method, path, **kwargs):
            nonlocal stream_opened
            stream_opened = True
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.headers = httpx.Headers({})
            mock_response.read.return_value = b"lazy"
            mock_response.close = MagicMock()
            yield mock_response

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={})
        assert stream_opened is False

        reader.read()
        assert stream_opened is True

    def test_stream_not_opened_until_context_entry(self):
        stream_opened = False

        @contextmanager
        def mock_stream(method, path, **kwargs):
            nonlocal stream_opened
            stream_opened = True
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.headers = httpx.Headers({})
            mock_response.read.return_value = b"lazy ctx"
            mock_response.close = MagicMock()
            yield mock_response

        client = MagicMock()
        client._stream = mock_stream

        reader = ObjectReader(client, "/objects/foo", params={})
        assert stream_opened is False

        with reader:
            assert stream_opened is True
