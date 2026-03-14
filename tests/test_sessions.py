"""Tests for Session resource."""

import warnings
from typing import ClassVar
from unittest.mock import patch

import httpx
import pytest

from tilde.resources.sessions import Session


class TestSessionCreation:
    def test_create_session(self, mock_api, repo):
        """POST .../sessions returns a Session with session_id."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(
                201,
                json={"session_id": "sess-abc-123"},
            )
        )
        session = repo.session()
        assert isinstance(session, Session)
        assert session.session_id == "sess-abc-123"

    def test_attach_session(self, repo):
        """repo.attach() returns a Session without making an API call."""
        session = repo.attach("sess-existing-456")
        assert isinstance(session, Session)
        assert session.session_id == "sess-existing-456"


class TestSessionCommitRollback:
    def test_commit(self, mock_api, repo):
        """POST .../sessions/{session_id} with message commits the session."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-1"})
        )
        commit_route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/sessions/sess-1"
        ).mock(return_value=httpx.Response(200, json={"commit_id": "commit-abc"}))
        session = repo.session()
        commit_id = session.commit("test commit")
        assert commit_id == "commit-abc"
        assert commit_route.called

    def test_rollback(self, mock_api, repo):
        """DELETE .../sessions/{session_id} rolls back the session."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-2"})
        )
        rollback_route = mock_api.delete(
            "/organizations/test-org/repositories/test-repo/sessions/sess-2"
        ).mock(return_value=httpx.Response(204))
        session = repo.session()
        session.rollback()
        assert rollback_route.called


class TestSessionContextManager:
    def test_commit_inside_context_manager(self, mock_api, repo):
        """Context manager allows explicit commit and does not rollback after."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-cm-1"})
        )
        commit_route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/sessions/sess-cm-1"
        ).mock(return_value=httpx.Response(200, json={"commit_id": "commit-cm"}))
        with repo.session() as session:
            assert session.session_id == "sess-cm-1"
            session.commit("explicit commit")
        assert commit_route.called

    def test_auto_rollback_on_error(self, mock_api, repo):
        """Context manager rolls back on exception."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-cm-2"})
        )
        rollback_route = mock_api.delete(
            "/organizations/test-org/repositories/test-repo/sessions/sess-cm-2"
        ).mock(return_value=httpx.Response(204))
        with pytest.raises(ValueError, match="boom"), repo.session():
            raise ValueError("boom")
        assert rollback_route.called

    def test_rollback_on_exit_without_commit(self, mock_api, repo):
        """Context manager rolls back if exiting without an explicit commit."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-cm-3"})
        )
        rollback_route = mock_api.delete(
            "/organizations/test-org/repositories/test-repo/sessions/sess-cm-3"
        ).mock(return_value=httpx.Response(204))
        with repo.session():
            pass  # no commit called
        assert rollback_route.called

    def test_no_double_rollback_after_commit(self, mock_api, repo):
        """If commit() is called explicitly, context manager does not rollback."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-cm-4"})
        )
        commit_route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/sessions/sess-cm-4"
        ).mock(return_value=httpx.Response(200, json={"commit_id": "commit-manual"}))
        rollback_route = mock_api.delete(
            "/organizations/test-org/repositories/test-repo/sessions/sess-cm-4"
        ).mock(return_value=httpx.Response(204))
        with repo.session() as session:
            session.commit("manual commit")
        assert commit_route.call_count == 1
        assert not rollback_route.called


class TestSessionApproval:
    APPROVAL_RESPONSE: ClassVar[dict[str, object]] = {
        "approval_required": True,
        "session_id": "sess-approve-1",
        "message": "Approval required for agent commits",
        "api_url": (
            "https://tilde.run/api/v1/organizations/test-org"
            "/repositories/test-repo/sessions/sess-approve-1/approve"
        ),
        "web_url": ("https://app.tilde.run/test-org/test-repo/approve/sess-approve-1"),
    }

    def test_commit_approval_required_block(self, mock_api, repo):
        """202 response triggers warning and polls until approved."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-approve-1"})
        )
        mock_api.post(
            "/organizations/test-org/repositories/test-repo/sessions/sess-approve-1"
        ).mock(return_value=httpx.Response(202, json=self.APPROVAL_RESPONSE))
        # First HEAD returns 200 (still pending), second returns 404 (approved).
        head_route = mock_api.head(
            "/organizations/test-org/repositories/test-repo/sessions/sess-approve-1/approve"
        ).mock(
            side_effect=[
                httpx.Response(200),
                httpx.Response(
                    404,
                    json={"message": "not found", "code": "not_found", "request_id": "r1"},
                ),
            ]
        )
        session = repo.session()
        with (
            patch("tilde.resources.sessions.time.sleep") as mock_sleep,
            warnings.catch_warnings(record=True) as w,
        ):
            warnings.simplefilter("always")
            commit_id = session.commit("agent changes")
        assert commit_id == ""
        assert len(w) == 1
        assert "Approval required" in str(w[0].message)
        assert "https://app.tilde.run/" in str(w[0].message)
        assert head_route.call_count == 2
        assert mock_sleep.call_count == 2
        assert session._committed is True

    def test_commit_approval_required_no_block(self, mock_api, repo):
        """202 with block_for_approval=False emits warning and returns immediately."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-approve-1"})
        )
        mock_api.post(
            "/organizations/test-org/repositories/test-repo/sessions/sess-approve-1"
        ).mock(return_value=httpx.Response(202, json=self.APPROVAL_RESPONSE))
        session = repo.session()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            commit_id = session.commit("agent changes", block_for_approval=False)
        assert commit_id is None
        assert len(w) == 1
        assert "Approval required" in str(w[0].message)
        assert session._committed is True

    def test_commit_approval_no_auto_rollback(self, mock_api, repo):
        """Context manager does not rollback after approval commit (block_for_approval=False)."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-approve-1"})
        )
        mock_api.post(
            "/organizations/test-org/repositories/test-repo/sessions/sess-approve-1"
        ).mock(return_value=httpx.Response(202, json=self.APPROVAL_RESPONSE))
        rollback_route = mock_api.delete(
            "/organizations/test-org/repositories/test-repo/sessions/sess-approve-1"
        ).mock(return_value=httpx.Response(204))
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            with repo.session() as session:
                session.commit("agent changes", block_for_approval=False)
        assert not rollback_route.called


class TestSessionUncommitted:
    def test_uncommitted_changes(self, mock_api, repo):
        """GET .../changes?session_id=... lists uncommitted changes."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-uc"})
        )
        mock_api.get("/organizations/test-org/repositories/test-repo/changes").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "path": "staged.txt",
                            "entry": {
                                "address": "addr-staged",
                                "size": 300,
                                "e_tag": "etag-s",
                                "content_type": "text/plain",
                            },
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        session = repo.session()
        items = list(session.uncommitted())
        assert len(items) == 1
        assert items[0].path == "staged.txt"
