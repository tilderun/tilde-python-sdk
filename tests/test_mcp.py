"""Tests for the Tilde MCP server tools."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from tilde._version import __version__
from tilde.mcp import server as mcp_server


def _call(tool_or_fn, **kwargs):
    """Call an MCP tool function, unwrapping FunctionTool if needed."""
    fn = getattr(tool_or_fn, "fn", tool_or_fn)
    return fn(**kwargs)


BASE_URL = "https://tilde.run/api/v1"
ORG = "test-org"
REPO = "test-repo"
REPOSITORY = f"{ORG}/{REPO}"
REPO_PATH = f"/organizations/{ORG}/repositories/{REPO}"


def _make_ctx(client_name: str | None = None, client_version: str | None = None) -> MagicMock:
    """Build a mock :class:`fastmcp.Context` with optional client info."""
    ctx = MagicMock()
    if client_name is not None:
        ctx.session.client_params.clientInfo.name = client_name
        ctx.session.client_params.clientInfo.version = client_version or "0.0.0"
    else:
        # No client info available
        ctx.session.client_params = None
    return ctx


@pytest.fixture()
def ctx() -> MagicMock:
    """A Context mock with no MCP client info."""
    return _make_ctx()


@pytest.fixture(autouse=True)
def _reset_server_state():
    """Clear module-level state between tests."""
    mcp_server._sessions.clear()
    if mcp_server._client is not None:
        mcp_server._client.close()
    mcp_server._client = None
    mcp_server._client_key = None
    mcp_server._client_ua = None
    yield
    mcp_server._sessions.clear()
    if mcp_server._client is not None:
        mcp_server._client.close()
    mcp_server._client = None
    mcp_server._client_key = None
    mcp_server._client_ua = None


@pytest.fixture(autouse=True)
def _agent_key_env(monkeypatch: pytest.MonkeyPatch):
    """Set a valid agent key by default; individual tests can override."""
    monkeypatch.setenv("TILDE_API_KEY", "cak-test-key")


@pytest.fixture()
def mock_api():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as rsps:
        yield rsps


# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------


class TestApiKeyValidation:
    def test_missing_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="not set"):
            mcp_server._validate_agent_key()

    def test_wrong_prefix(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TILDE_API_KEY", "sk-xxx")
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="agent key"):
            mcp_server._validate_agent_key()

    def test_valid_agent_key(self):
        key = mcp_server._validate_agent_key()
        assert key == "cak-test-key"


# ---------------------------------------------------------------------------
# list_repositories
# ---------------------------------------------------------------------------


class TestListRepositories:
    def test_happy_path(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.get(f"/organizations/{ORG}/repositories").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "repo-1",
                            "organization_id": "org-1",
                            "name": "repo-one",
                            "description": "First repo",
                            "visibility": "private",
                            "created_by": "user-1",
                            "created_at": "2025-06-01T10:00:00+00:00",
                        },
                        {
                            "id": "repo-2",
                            "organization_id": "org-1",
                            "name": "repo-two",
                            "description": "",
                            "visibility": "public",
                            "created_by": "user-1",
                            "created_at": None,
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        result = _call(mcp_server.list_repositories, organization=ORG, ctx=ctx)
        assert len(result) == 2
        assert result[0]["id"] == "repo-1"
        assert result[0]["name"] == "repo-one"
        assert result[0]["description"] == "First repo"
        assert result[0]["visibility"] == "private"
        assert result[0]["created_at"] == "2025-06-01T10:00:00+00:00"
        assert result[1]["name"] == "repo-two"
        assert result[1]["created_at"] is None

    def test_empty(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.get(f"/organizations/{ORG}/repositories").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        result = _call(mcp_server.list_repositories, organization=ORG, ctx=ctx)
        assert result == []


# ---------------------------------------------------------------------------
# create_repository
# ---------------------------------------------------------------------------


class TestCreateRepository:
    def test_happy_path(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.post(f"/organizations/{ORG}/repositories").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "repo-new",
                    "organization_id": "org-1",
                    "name": "my-repo",
                    "description": "A new repo",
                    "visibility": "private",
                    "created_by": "user-1",
                    "created_at": "2025-08-01T12:00:00+00:00",
                },
            )
        )
        result = _call(
            mcp_server.create_repository,
            organization=ORG,
            name="my-repo",
            description="A new repo",
            ctx=ctx,
        )
        assert result["id"] == "repo-new"
        assert result["name"] == "my-repo"
        assert result["description"] == "A new repo"
        assert result["visibility"] == "private"
        assert result["created_at"] == "2025-08-01T12:00:00+00:00"

    def test_invalid_visibility(self, ctx: MagicMock):
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="visibility must be"):
            _call(
                mcp_server.create_repository,
                organization=ORG,
                name="x",
                ctx=ctx,
                visibility="internal",
            )


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    def test_happy_path(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.post(f"{REPO_PATH}/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-1"})
        )
        result = _call(mcp_server.create_session, repository=REPOSITORY, ctx=ctx)
        assert result == {"session_id": "sess-1", "repository": REPOSITORY}


# ---------------------------------------------------------------------------
# list_objects
# ---------------------------------------------------------------------------


class TestListObjects:
    def test_happy_path(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.get(f"{REPO_PATH}/objects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"path": "data/", "type": "prefix"},
                        {
                            "path": "data/file.csv",
                            "type": "object",
                            "entry": {
                                "address": "addr1",
                                "size": 1024,
                                "e_tag": "etag1",
                                "content_type": "text/csv",
                                "last_modified": "2025-06-15T10:30:00+00:00",
                                "metadata": {"author": "alice"},
                                "source_metadata": {
                                    "connector_id": "conn-1",
                                    "connector_type": "s3",
                                    "source_path": "s3://bucket/file.csv",
                                    "version_id": "v1",
                                    "source_etag": "abc",
                                    "import_time": "2025-06-15T09:00:00+00:00",
                                    "import_job_id": "job-1",
                                },
                            },
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        # Seed a session so we don't need a create call
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.list_objects,
            repository=REPOSITORY,
            session_id="sess-1",
            ctx=ctx,
            prefix="",
            delimiter="/",
            amount=100,
        )
        assert len(result) == 2
        # Prefix entry has only path and type
        prefix_item = result[0]
        assert prefix_item["path"] == "data/"
        assert prefix_item["type"] == "prefix"
        assert "size" not in prefix_item

        # Object entry has full metadata
        obj_item = result[1]
        assert obj_item["path"] == "data/file.csv"
        assert obj_item["type"] == "object"
        assert obj_item["size"] == 1024
        assert obj_item["last_modified"] == "2025-06-15T10:30:00+00:00"
        assert obj_item["content_type"] == "text/csv"
        assert obj_item["metadata"] == {"author": "alice"}
        sm = obj_item["source_metadata"]
        assert sm["connector_type"] == "s3"
        assert sm["source_path"] == "s3://bucket/file.csv"

    def test_object_without_source_metadata(self, mock_api: respx.MockRouter, ctx: MagicMock):
        """Objects without source_metadata should return None for that field."""
        mock_api.get(f"{REPO_PATH}/objects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "path": "plain.txt",
                            "type": "object",
                            "entry": {
                                "address": "addr2",
                                "size": 42,
                                "e_tag": "etag2",
                                "content_type": "text/plain",
                            },
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(mcp_server.list_objects, repository=REPOSITORY, session_id="sess-1", ctx=ctx)
        assert len(result) == 1
        assert result[0]["size"] == 42
        assert result[0]["source_metadata"] is None
        assert result[0]["metadata"] == {}

    def test_amount_truncation(self, mock_api: respx.MockRouter, ctx: MagicMock):
        """Only ``amount`` items should be returned even if more exist."""
        mock_api.get(f"{REPO_PATH}/objects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"path": "a.txt", "type": "object", "entry": {"size": 1}},
                        {"path": "b.txt", "type": "object", "entry": {"size": 2}},
                        {"path": "c.txt", "type": "object", "entry": {"size": 3}},
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.list_objects,
            repository=REPOSITORY,
            session_id="sess-1",
            ctx=ctx,
            amount=2,
        )
        assert len(result) == 2

    def test_amount_non_positive_rejected(self, ctx: MagicMock):
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="positive integer"):
            _call(
                mcp_server.list_objects,
                repository=REPOSITORY,
                session_id="sess-1",
                ctx=ctx,
                amount=0,
            )


# ---------------------------------------------------------------------------
# get_object
# ---------------------------------------------------------------------------


class TestGetObject:
    def test_utf8_content(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.get(f"{REPO_PATH}/object").mock(
            return_value=httpx.Response(
                200,
                content=b"hello world",
                headers={"content-type": "text/plain"},
            )
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.get_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="hello.txt",
            ctx=ctx,
        )
        assert result["encoding"] == "utf-8"
        assert result["content"] == "hello world"
        assert result["content_type"] == "text/plain"

    def test_binary_content(self, mock_api: respx.MockRouter, ctx: MagicMock):
        raw = bytes(range(256))
        mock_api.get(f"{REPO_PATH}/object").mock(
            return_value=httpx.Response(
                200,
                content=raw,
                headers={"content-type": "application/octet-stream"},
            )
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.get_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="binary.bin",
            ctx=ctx,
        )
        assert result["encoding"] == "base64"
        assert base64.b64decode(result["content"]) == raw
        assert result["content_type"] == "application/octet-stream"

    def test_binary_content_default_content_type(self, mock_api: respx.MockRouter, ctx: MagicMock):
        """When no content-type header, binary falls back to application/octet-stream."""
        raw = b"\x80\x81\x82"
        mock_api.get(f"{REPO_PATH}/object").mock(return_value=httpx.Response(200, content=raw))
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.get_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="bin.dat",
            ctx=ctx,
        )
        assert result["encoding"] == "base64"
        assert result["content_type"] == "application/octet-stream"

    def test_utf8_content_default_content_type(self, mock_api: respx.MockRouter, ctx: MagicMock):
        """When no content-type header, utf-8 falls back to text/plain; charset=utf-8."""
        mock_api.get(f"{REPO_PATH}/object").mock(return_value=httpx.Response(200, content=b"abc"))
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.get_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="text.txt",
            ctx=ctx,
        )
        assert result["encoding"] == "utf-8"
        assert result["content_type"] == "text/plain; charset=utf-8"


# ---------------------------------------------------------------------------
# head_object
# ---------------------------------------------------------------------------


class TestHeadObject:
    def test_happy_path(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.head(f"{REPO_PATH}/object").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "content-type": "text/csv",
                    "content-length": "2048",
                },
            )
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.head_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="data/report.csv",
            ctx=ctx,
        )
        assert result == {
            "path": "data/report.csv",
            "content_type": "text/csv",
            "size": 2048,
        }

    def test_missing_headers(self, mock_api: respx.MockRouter, ctx: MagicMock):
        """When headers are absent, values should be None."""
        mock_api.head(f"{REPO_PATH}/object").mock(return_value=httpx.Response(200))
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.head_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="unknown.bin",
            ctx=ctx,
        )
        assert result["path"] == "unknown.bin"
        assert result["content_type"] is None
        assert result["size"] is None


# ---------------------------------------------------------------------------
# put_object
# ---------------------------------------------------------------------------


class TestPutObject:
    def _mock_presign_put(self, mock_api: respx.MockRouter, path: str, etag: str) -> None:
        """Set up stage → presigned upload → finalize mocks."""
        mock_api.post(f"{REPO_PATH}/object/stage").mock(
            return_value=httpx.Response(
                200,
                json={
                    "upload_url": "https://s3.example.com/bucket/staged",
                    "physical_address": "s3://bucket/staged",
                    "signature": "sig-test",
                    "expires_at": "2026-02-24T00:00:00Z",
                },
            )
        )
        mock_api.put(url="https://s3.example.com/bucket/staged").mock(
            return_value=httpx.Response(200)
        )
        mock_api.put(f"{REPO_PATH}/object/finalize").mock(
            return_value=httpx.Response(201, json={"path": path, "etag": etag})
        )

    def test_utf8(self, mock_api: respx.MockRouter, ctx: MagicMock):
        self._mock_presign_put(mock_api, "data/file.csv", "etag-1")
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.put_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="data/file.csv",
            content="hello",
            ctx=ctx,
            encoding="utf-8",
        )
        assert result == {"path": "data/file.csv", "etag": "etag-1"}

    def test_base64(self, mock_api: respx.MockRouter, ctx: MagicMock):
        raw = b"\x00\x01\x02"
        encoded = base64.b64encode(raw).decode("ascii")
        self._mock_presign_put(mock_api, "binary.bin", "etag-b")
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.put_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="binary.bin",
            content=encoded,
            ctx=ctx,
            encoding="base64",
        )
        assert result == {"path": "binary.bin", "etag": "etag-b"}

    def test_invalid_encoding(self, ctx: MagicMock):
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="encoding must be"):
            _call(
                mcp_server.put_object,
                repository=REPOSITORY,
                session_id="sess-1",
                path="x.txt",
                content="data",
                ctx=ctx,
                encoding="latin-1",
            )


# ---------------------------------------------------------------------------
# delete_object
# ---------------------------------------------------------------------------


class TestDeleteObject:
    def test_happy_path(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.delete(f"{REPO_PATH}/object").mock(return_value=httpx.Response(204))
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.delete_object,
            repository=REPOSITORY,
            session_id="sess-1",
            path="old.csv",
            ctx=ctx,
        )
        assert result == {"status": "deleted", "path": "old.csv"}


# ---------------------------------------------------------------------------
# commit_session
# ---------------------------------------------------------------------------


class TestCommitSession:
    def test_direct_commit(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.post(f"{REPO_PATH}/sessions/sess-1").mock(
            return_value=httpx.Response(200, json={"commit_id": "abc123"})
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.commit_session,
            repository=REPOSITORY,
            session_id="sess-1",
            message="update data",
            ctx=ctx,
        )
        assert result == {
            "status": "committed",
            "commit_id": "abc123",
            "web_url": None,
        }
        # Session should be removed from cache
        assert (REPOSITORY, "sess-1") not in mcp_server._sessions

    def test_approval_required(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.post(f"{REPO_PATH}/sessions/sess-1").mock(
            return_value=httpx.Response(
                202,
                json={
                    "approval_required": True,
                    "web_url": "https://tilde.run/test-org/test-repo/approve/sess-1",
                },
            )
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.commit_session,
            repository=REPOSITORY,
            session_id="sess-1",
            message="agent changes",
            ctx=ctx,
        )
        assert result["status"] == "approval_required"
        assert result["commit_id"] is None
        assert "tilde.run" in result["web_url"]
        assert (REPOSITORY, "sess-1") not in mcp_server._sessions


# ---------------------------------------------------------------------------
# close_session
# ---------------------------------------------------------------------------


class TestCloseSession:
    def test_rollback(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.delete(f"{REPO_PATH}/sessions/sess-1").mock(return_value=httpx.Response(204))
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.close_session,
            repository=REPOSITORY,
            session_id="sess-1",
            ctx=ctx,
        )
        assert result == {"status": "rolled_back", "session_id": "sess-1"}
        assert (REPOSITORY, "sess-1") not in mcp_server._sessions

    def test_already_closed(self, mock_api: respx.MockRouter, ctx: MagicMock):
        """If the session is already closed, return idempotent response."""
        mock_api.delete(f"{REPO_PATH}/sessions/sess-1").mock(
            return_value=httpx.Response(
                404, json={"message": "not found", "code": "not_found", "request_id": "r1"}
            )
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        result = _call(
            mcp_server.close_session,
            repository=REPOSITORY,
            session_id="sess-1",
            ctx=ctx,
        )
        assert result == {"status": "already_closed", "session_id": "sess-1"}
        assert (REPOSITORY, "sess-1") not in mcp_server._sessions


# ---------------------------------------------------------------------------
# Session reattach (cache miss)
# ---------------------------------------------------------------------------


class TestSessionReattach:
    def test_cache_miss_attaches(self, mock_api: respx.MockRouter, ctx: MagicMock):
        """When the session isn't cached, ``attach()`` is used transparently."""
        mock_api.delete(f"{REPO_PATH}/object").mock(return_value=httpx.Response(204))
        # No pre-seeded session — should reattach automatically
        result = _call(
            mcp_server.delete_object,
            repository=REPOSITORY,
            session_id="sess-new",
            path="x.csv",
            ctx=ctx,
        )
        assert result["status"] == "deleted"
        assert (REPOSITORY, "sess-new") in mcp_server._sessions


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


class TestErrorMapping:
    def test_404_maps_to_tool_error(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.get(f"{REPO_PATH}/object").mock(
            return_value=httpx.Response(
                404, json={"message": "not found", "code": "not_found", "request_id": "r1"}
            )
        )
        mcp_server._sessions[(REPOSITORY, "sess-1")] = (
            mcp_server._get_client("cak-test-key").repository(REPOSITORY).attach("sess-1")
        )
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Not found"):
            _call(
                mcp_server.get_object,
                repository=REPOSITORY,
                session_id="sess-1",
                path="missing.txt",
                ctx=ctx,
            )

    def test_401_maps_to_auth_error(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.post(f"{REPO_PATH}/sessions").mock(
            return_value=httpx.Response(
                401, json={"message": "unauthorized", "code": "unauthorized", "request_id": "r2"}
            )
        )
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Authentication failed"):
            _call(mcp_server.create_session, repository=REPOSITORY, ctx=ctx)

    def test_403_maps_to_permission_denied(self, mock_api: respx.MockRouter, ctx: MagicMock):
        mock_api.post(f"{REPO_PATH}/sessions").mock(
            return_value=httpx.Response(
                403, json={"message": "forbidden", "code": "forbidden", "request_id": "r3"}
            )
        )
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Permission denied"):
            _call(mcp_server.create_session, repository=REPOSITORY, ctx=ctx)


# ---------------------------------------------------------------------------
# Key change invalidates session cache
# ---------------------------------------------------------------------------


class TestKeyRotation:
    def test_key_change_clears_sessions(
        self, mock_api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch, ctx: MagicMock
    ):
        """Changing the API key should recreate the client and clear cached sessions."""
        # Seed a session under key A
        mock_api.post(f"{REPO_PATH}/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-a"})
        )
        _call(mcp_server.create_session, repository=REPOSITORY, ctx=ctx)
        assert (REPOSITORY, "sess-a") in mcp_server._sessions
        old_client = mcp_server._client

        # Change key to B
        monkeypatch.setenv("TILDE_API_KEY", "cak-other-key")

        mock_api.post(f"{REPO_PATH}/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-b"})
        )
        _call(mcp_server.create_session, repository=REPOSITORY, ctx=ctx)

        # Old session should be gone, new client created
        assert (REPOSITORY, "sess-a") not in mcp_server._sessions
        assert (REPOSITORY, "sess-b") in mcp_server._sessions
        assert mcp_server._client is not old_client


# ---------------------------------------------------------------------------
# User-Agent header
# ---------------------------------------------------------------------------


class TestMcpUserAgent:
    def test_mcp_user_agent_in_requests(self, mock_api: respx.MockRouter, ctx: MagicMock):
        """Requests via MCP tools should include tilde-mcp in the User-Agent."""
        mock_api.post(f"{REPO_PATH}/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-1"})
        )
        _call(mcp_server.create_session, repository=REPOSITORY, ctx=ctx)
        ua = mock_api.calls.last.request.headers.get("user-agent", "")
        assert "tilde-python-sdk/" in ua
        assert "tilde-mcp/" in ua

    def test_mcp_user_agent_includes_client_info(self, mock_api: respx.MockRouter):
        """When the MCP client provides its identity, it appears in the UA."""
        ctx_with_client = _make_ctx(client_name="claude-desktop", client_version="1.2.3")
        mock_api.post(f"{REPO_PATH}/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-1"})
        )
        _call(mcp_server.create_session, repository=REPOSITORY, ctx=ctx_with_client)
        ua = mock_api.calls.last.request.headers.get("user-agent", "")
        assert "tilde-mcp/" in ua
        assert "claude-desktop/1.2.3" in ua

    def test_build_mcp_user_agent_no_client_info(self):
        """Without client info, only tilde-mcp is included."""
        ctx = _make_ctx()
        ua = mcp_server._build_mcp_user_agent(ctx)
        assert ua.startswith("tilde-mcp/")
        assert "claude" not in ua.lower()

    def test_build_mcp_user_agent_with_client_info(self):
        """With client info, both tilde-mcp and client identity are included."""
        ctx = _make_ctx(client_name="claude-desktop", client_version="1.2.3")
        ua = mcp_server._build_mcp_user_agent(ctx)
        assert ua == f"tilde-mcp/{__version__} claude-desktop/1.2.3"
