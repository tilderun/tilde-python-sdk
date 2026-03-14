"""Tests for tilde.client.Client."""

import httpx
import pytest
import respx
from httpx import Response

from tilde._version import __version__
from tilde.client import Client
from tilde.exceptions import (
    AuthenticationError,
    BadRequestError,
    ConfigurationError,
    NotFoundError,
    ServerError,
    TransportError,
)

BASE_URL = "https://tilde.run/api/v1"


# ---------------------------------------------------------------------------
# Authorization header
# ---------------------------------------------------------------------------


class TestAuthorizationHeader:
    """_request must attach 'Authorization: Bearer <api_key>'."""

    def test_authorization_header_is_set(self, mock_api, client):
        mock_api.get("/healthcheck").mock(return_value=Response(200, json={"status": "ok"}))

        client._get_json("/healthcheck")

        request = mock_api.calls.last.request
        assert request.headers["authorization"] == "Bearer test-key"


# ---------------------------------------------------------------------------
# User-Agent header
# ---------------------------------------------------------------------------


class TestUserAgentHeader:
    """Requests must carry a User-Agent that identifies the SDK."""

    def test_user_agent_is_present(self, mock_api, client):
        mock_api.get("/healthcheck").mock(return_value=Response(200, json={"ok": True}))

        client._get_json("/healthcheck")

        ua = mock_api.calls.last.request.headers.get("user-agent", "")
        # The UA should mention "tilde" (case-insensitive)
        assert "tilde" in ua.lower()

    def test_default_user_agent_has_no_extra(self, mock_api):
        mock_api.get("/healthcheck").mock(return_value=Response(200, json={"ok": True}))
        c = Client(api_key="test-key")
        c._get_json("/healthcheck")
        ua = mock_api.calls.last.request.headers.get("user-agent", "")
        assert ua == f"tilde-python-sdk/{__version__}"

    def test_extra_user_agent_appended(self, mock_api):
        mock_api.get("/healthcheck").mock(return_value=Response(200, json={"ok": True}))
        c = Client(api_key="test-key", extra_user_agent="tilde-mcp/0.3.0 claude-desktop/1.2.3")
        c._get_json("/healthcheck")
        ua = mock_api.calls.last.request.headers.get("user-agent", "")
        assert ua == f"tilde-python-sdk/{__version__} tilde-mcp/0.3.0 claude-desktop/1.2.3"


# ---------------------------------------------------------------------------
# ConfigurationError when api_key is missing
# ---------------------------------------------------------------------------


class TestConfigurationError:
    """Client must raise ConfigurationError when no api_key is available at request time."""

    def test_none_api_key(self, mock_api, monkeypatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        mock_api.get("/test").mock(return_value=httpx.Response(200, json={}))
        c = Client(api_key=None)
        with pytest.raises(ConfigurationError):
            c._get("/test")

    def test_no_api_key_at_all(self, mock_api, monkeypatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        mock_api.get("/test").mock(return_value=httpx.Response(200, json={}))
        c = Client()
        with pytest.raises(ConfigurationError):
            c._get("/test")


# ---------------------------------------------------------------------------
# _raise_for_status  -- status code mapping
# ---------------------------------------------------------------------------


class TestRaiseForStatusMapping:
    """HTTP error codes must map to the correct exception type."""

    @pytest.mark.parametrize(
        "status_code, exc_class",
        [
            (400, BadRequestError),
            (401, AuthenticationError),
            (404, NotFoundError),
            (500, ServerError),
        ],
    )
    def test_status_code_to_exception(self, mock_api, client, status_code, exc_class):
        mock_api.get("/fail").mock(
            return_value=Response(
                status_code,
                json={
                    "message": "something went wrong",
                    "code": "ERR_TEST",
                    "request_id": "req-abc-123",
                },
            )
        )

        with pytest.raises(exc_class):
            client._get_json("/fail")


# ---------------------------------------------------------------------------
# _raise_for_status  -- JSON error body parsing
# ---------------------------------------------------------------------------


class TestRaiseForStatusJsonBody:
    """When the error response is JSON, message/code/request_id are parsed."""

    def test_json_error_body_fields(self, mock_api, client):
        mock_api.get("/bad").mock(
            return_value=Response(
                400,
                json={
                    "message": "invalid parameter",
                    "code": "ERR_VALIDATION",
                    "request_id": "req-xyz-789",
                },
            )
        )

        with pytest.raises(BadRequestError) as exc_info:
            client._get_json("/bad")

        err = exc_info.value
        assert "invalid parameter" in str(err)
        # If the exception exposes structured attributes, check them
        if hasattr(err, "code"):
            assert err.code == "ERR_VALIDATION"
        if hasattr(err, "request_id"):
            assert err.request_id == "req-xyz-789"


# ---------------------------------------------------------------------------
# _raise_for_status  -- non-JSON response body
# ---------------------------------------------------------------------------


class TestRaiseForStatusNonJson:
    """Error responses with non-JSON bodies must still raise the right error."""

    def test_plain_text_error_body(self, mock_api, client):
        mock_api.get("/text-err").mock(
            return_value=Response(
                500,
                text="Internal Server Error",
                headers={"content-type": "text/plain"},
            )
        )

        with pytest.raises(ServerError):
            client._get_json("/text-err")


# ---------------------------------------------------------------------------
# TransportError wrapping
# ---------------------------------------------------------------------------


class TestTransportError:
    """httpx.TransportError must be wrapped in tilde.TransportError."""

    def test_transport_error_is_wrapped(self, mock_api, client):
        mock_api.get("/down").mock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(TransportError):
            client._get_json("/down")


# ---------------------------------------------------------------------------
# Context manager / close
# ---------------------------------------------------------------------------


class TestContextManager:
    """Client can be used as a context manager and .close() is idempotent."""

    def test_context_manager_closes(self):
        with respx.mock(base_url=BASE_URL, assert_all_called=False):
            with Client(api_key="ctx-key") as c:
                assert c is not None
            # After exiting, calling close again should not raise
            c.close()

    def test_close_is_idempotent(self):
        with respx.mock(base_url=BASE_URL, assert_all_called=False):
            c = Client(api_key="idem-key")
            c.close()
            c.close()  # second call must not raise


# ---------------------------------------------------------------------------
# _get_json / _post_json helpers
# ---------------------------------------------------------------------------


class TestGetJson:
    """_get_json sends GET and returns parsed JSON."""

    def test_get_json_returns_dict(self, mock_api, client):
        payload = {"id": 1, "name": "alice"}
        mock_api.get("/users/1").mock(return_value=Response(200, json=payload))

        result = client._get_json("/users/1")
        assert result == payload

    def test_get_json_with_params(self, mock_api, client):
        payload = {"items": []}
        mock_api.get("/search").mock(return_value=Response(200, json=payload))

        result = client._get_json("/search", params={"q": "hello"})

        assert result == payload
        sent_url = str(mock_api.calls.last.request.url)
        assert "q=hello" in sent_url


class TestPostJson:
    """_post_json sends POST with a JSON body and returns parsed JSON."""

    def test_post_json_sends_body(self, mock_api, client):
        mock_api.post("/items").mock(return_value=Response(201, json={"id": 42}))

        result = client._post_json("/items", json={"name": "widget"})

        assert result == {"id": 42}
        sent = mock_api.calls.last.request
        assert b"widget" in sent.content
