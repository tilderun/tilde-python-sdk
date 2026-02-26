"""Tests for the cerebral.exceptions module."""

from typing import ClassVar

import pytest

from cerebral.exceptions import (
    APIError,
    AuthenticationError,
    BadRequestError,
    CerebralError,
    ConfigurationError,
    ConflictError,
    ForbiddenError,
    GoneError,
    LockedError,
    NotFoundError,
    PreconditionFailedError,
    SerializationError,
    ServerError,
    TransportError,
    api_error_for_status,
)

# ---------------------------------------------------------------------------
# Base hierarchy
# ---------------------------------------------------------------------------


class TestCerebralErrorHierarchy:
    """CerebralError is the root of the exception tree."""

    def test_cerebral_error_is_exception(self):
        assert issubclass(CerebralError, Exception)

    def test_configuration_error_inherits_cerebral_error(self):
        assert issubclass(ConfigurationError, CerebralError)

    def test_transport_error_inherits_cerebral_error(self):
        assert issubclass(TransportError, CerebralError)

    def test_serialization_error_inherits_cerebral_error(self):
        assert issubclass(SerializationError, CerebralError)

    def test_api_error_inherits_cerebral_error(self):
        assert issubclass(APIError, CerebralError)


# ---------------------------------------------------------------------------
# APIError
# ---------------------------------------------------------------------------


class TestAPIError:
    """APIError carries rich request/response metadata."""

    def _make_error(self, **overrides):
        defaults = dict(
            status_code=500,
            message="something broke",
            code="internal_error",
            request_id="req-abc-123",
            method="POST",
            url="https://cerebral.storage/api/v1/objects",
            response_text="raw body",
        )
        defaults.update(overrides)
        return APIError(**defaults)

    def test_attributes_are_stored(self):
        err = self._make_error()
        assert err.status_code == 500
        assert err.message == "something broke"
        assert err.code == "internal_error"
        assert err.request_id == "req-abc-123"
        assert err.method == "POST"
        assert err.url == "https://cerebral.storage/api/v1/objects"
        assert err.response_text == "raw body"

    def test_response_text_truncated_to_500_chars(self):
        long_body = "x" * 1000
        err = self._make_error(response_text=long_body)
        assert len(err.response_text) <= 500

    def test_str_includes_method_url_status_and_message(self):
        err = self._make_error(
            method="GET",
            url="https://example.com/endpoint",
            status_code=404,
            message="not found",
        )
        text = str(err)
        assert "GET" in text
        assert "https://example.com/endpoint" in text
        assert "404" in text
        assert "not found" in text


# ---------------------------------------------------------------------------
# APIError subclasses & default status codes
# ---------------------------------------------------------------------------


class TestAPIErrorSubclasses:
    """Each HTTP-specific error inherits from APIError."""

    @pytest.mark.parametrize(
        "cls, expected_status",
        [
            (BadRequestError, 400),
            (AuthenticationError, 401),
            (ForbiddenError, 403),
            (NotFoundError, 404),
            (ConflictError, 409),
            (GoneError, 410),
            (PreconditionFailedError, 412),
            (LockedError, 423),
        ],
    )
    def test_subclass_inherits_api_error(self, cls, expected_status):
        assert issubclass(cls, APIError)

    def test_server_error_inherits_api_error(self):
        assert issubclass(ServerError, APIError)


# ---------------------------------------------------------------------------
# api_error_for_status factory
# ---------------------------------------------------------------------------


class TestApiErrorForStatus:
    """The factory function returns the correct subclass for a given status."""

    _COMMON_KWARGS: ClassVar[dict[str, str]] = dict(
        message="msg",
        code="err",
        request_id="rid",
        method="GET",
        url="https://example.com",
        response_text="body",
    )

    @pytest.mark.parametrize(
        "status, expected_cls",
        [
            (400, BadRequestError),
            (401, AuthenticationError),
            (403, ForbiddenError),
            (404, NotFoundError),
            (409, ConflictError),
            (410, GoneError),
            (412, PreconditionFailedError),
            (423, LockedError),
        ],
    )
    def test_maps_status_to_subclass(self, status, expected_cls):
        err = api_error_for_status(status_code=status, **self._COMMON_KWARGS)
        assert isinstance(err, expected_cls)
        assert isinstance(err, APIError)

    @pytest.mark.parametrize("status", [500, 502, 503, 504])
    def test_5xx_returns_server_error(self, status):
        err = api_error_for_status(status_code=status, **self._COMMON_KWARGS)
        assert isinstance(err, ServerError)

    def test_unmapped_4xx_returns_api_error(self):
        err = api_error_for_status(status_code=418, **self._COMMON_KWARGS)
        assert type(err) is APIError

    def test_factory_preserves_attributes(self):
        err = api_error_for_status(
            status_code=404,
            message="not found",
            code="not_found",
            request_id="r1",
            method="DELETE",
            url="https://example.com/thing",
            response_text="nope",
        )
        assert err.status_code == 404
        assert err.message == "not found"
        assert err.method == "DELETE"


# ---------------------------------------------------------------------------
# TransportError
# ---------------------------------------------------------------------------


class TestTransportError:
    """TransportError wraps a lower-level cause via __cause__."""

    def test_stores_cause_via_dunder_cause(self):
        original = ConnectionError("connection refused")
        err = TransportError("transport failed", cause=original)
        assert err.__cause__ is original

    def test_cause_defaults_to_none(self):
        err = TransportError("boom", cause=None)
        assert err.__cause__ is None

    def test_inherits_cerebral_error(self):
        err = TransportError("boom", cause=None)
        assert isinstance(err, CerebralError)
