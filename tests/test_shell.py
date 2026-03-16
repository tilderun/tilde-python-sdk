"""Tests for Shell (interactive sandbox via WebSocket)."""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tilde._output_stream import OutputStream
from tilde.exceptions import CommandError, SandboxError
from tilde.models import RunResult

BASE_PATH = "/organizations/test-org/repositories/test-repo/sandboxes"


def _mock_status(mock_api, sandbox_id, state, **overrides):
    """Register a mock status endpoint for a sandbox."""
    data = {
        "status": state,
        "status_reason": "",
        "exit_code": overrides.get("exit_code"),
        "commit_id": overrides.get("commit_id", ""),
        "web_url": overrides.get("web_url", ""),
    }
    mock_api.get(f"{BASE_PATH}/{sandbox_id}/status").mock(
        return_value=httpx.Response(200, json=data)
    )


def _create_sandbox_route(mock_api, sandbox_id="sbx-shell"):
    return mock_api.post(BASE_PATH).mock(
        return_value=httpx.Response(201, json={"sandbox_id": sandbox_id})
    )


class TestShellRun:
    @patch("tilde.resources.shell.ws_connect")
    def test_run_captures_output(self, mock_ws_connect, mock_api, repo):
        """run() captures stdout and exit code from WebSocket."""
        _create_sandbox_route(mock_api, "sbx-run")
        # First call: running (for __enter__), second: committed (for __exit__)
        mock_api.get(f"{BASE_PATH}/sbx-run/status").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "status": "running",
                        "exit_code": None,
                        "commit_id": "",
                        "web_url": "",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "status": "committed",
                        "exit_code": 0,
                        "commit_id": "c-1",
                        "web_url": "",
                    },
                ),
            ]
        )

        mock_ws = MagicMock()
        mock_ws_connect.return_value = mock_ws

        # Simulate WebSocket recv: the shell echoes back the command and markers
        def make_recv(cmd_output, exit_code=0):
            marker_holder = {}

            def recv_side_effect(timeout=None):
                # First call returns the full output with markers
                if "marker" not in marker_holder:
                    # We need to extract the marker from the sent command
                    sent = mock_ws.send.call_args_list[-1][0][0]
                    # Parse marker from the sent wrapped command
                    begin_idx = sent.index("__TILDE_BEGIN_") + len("__TILDE_BEGIN_")
                    end_idx = sent.index("__", begin_idx)
                    marker = sent[begin_idx:end_idx]
                    marker_holder["marker"] = marker
                    begin_m = f"__TILDE_BEGIN_{marker}__"
                    end_m = f"__TILDE_END_{marker}__"
                    return f"{cmd_output}\n{begin_m}\n{exit_code}\n{end_m}\n"
                return ""

            return recv_side_effect

        mock_ws.recv.side_effect = make_recv("hello world")

        with repo.shell(image="alpine:latest") as sh:
            result = sh.run("echo hello world")

        assert isinstance(result, RunResult)
        assert result.exit_code == 0
        assert isinstance(result.stdout, OutputStream)
        assert "hello world" in result.stdout.text()

    @patch("tilde.resources.shell.ws_connect")
    def test_run_check_raises_on_nonzero(self, mock_ws_connect, mock_api, repo):
        """run(check=True) raises CommandError on non-zero exit."""
        _create_sandbox_route(mock_api, "sbx-fail")
        mock_api.get(f"{BASE_PATH}/sbx-fail/status").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "status": "running",
                        "exit_code": None,
                        "commit_id": "",
                        "web_url": "",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "status": "committed",
                        "exit_code": 0,
                        "commit_id": "c-2",
                        "web_url": "",
                    },
                ),
            ]
        )

        mock_ws = MagicMock()
        mock_ws_connect.return_value = mock_ws

        def recv_side_effect(timeout=None):
            sent = mock_ws.send.call_args_list[-1][0][0]
            begin_idx = sent.index("__TILDE_BEGIN_") + len("__TILDE_BEGIN_")
            end_idx = sent.index("__", begin_idx)
            marker = sent[begin_idx:end_idx]
            begin_m = f"__TILDE_BEGIN_{marker}__"
            end_m = f"__TILDE_END_{marker}__"
            return f"error output\n{begin_m}\n1\n{end_m}\n"

        mock_ws.recv.side_effect = recv_side_effect

        with repo.shell(image="alpine:latest") as sh:
            with pytest.raises(CommandError) as exc_info:
                sh.run("false", check=True)
            assert exc_info.value.result.exit_code == 1
            assert exc_info.value.command == "false"

    @patch("tilde.resources.shell.ws_connect")
    def test_run_check_false_no_raise(self, mock_ws_connect, mock_api, repo):
        """run(check=False) returns result even on non-zero exit."""
        _create_sandbox_route(mock_api, "sbx-nocheck")
        mock_api.get(f"{BASE_PATH}/sbx-nocheck/status").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "status": "running",
                        "exit_code": None,
                        "commit_id": "",
                        "web_url": "",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "status": "committed",
                        "exit_code": 0,
                        "commit_id": "c-3",
                        "web_url": "",
                    },
                ),
            ]
        )

        mock_ws = MagicMock()
        mock_ws_connect.return_value = mock_ws

        def recv_side_effect(timeout=None):
            sent = mock_ws.send.call_args_list[-1][0][0]
            begin_idx = sent.index("__TILDE_BEGIN_") + len("__TILDE_BEGIN_")
            end_idx = sent.index("__", begin_idx)
            marker = sent[begin_idx:end_idx]
            return f"\n__TILDE_BEGIN_{marker}__\n42\n__TILDE_END_{marker}__\n"

        mock_ws.recv.side_effect = recv_side_effect

        with repo.shell(image="alpine:latest") as sh:
            result = sh.run("exit 42")
        assert result.exit_code == 42


class TestShellContextManager:
    @patch("tilde.resources.shell.ws_connect")
    def test_cancel_on_exception(self, mock_ws_connect, mock_api, repo):
        """Shell cancels sandbox when exception occurs in context."""
        _create_sandbox_route(mock_api, "sbx-exc")
        mock_api.get(f"{BASE_PATH}/sbx-exc/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "running",
                    "exit_code": None,
                    "commit_id": "",
                    "web_url": "",
                },
            )
        )
        cancel_route = mock_api.delete(f"{BASE_PATH}/sbx-exc").mock(
            return_value=httpx.Response(202, json={"message": "cancelled"})
        )

        mock_ws = MagicMock()
        mock_ws_connect.return_value = mock_ws

        with pytest.raises(ValueError, match="test error"), repo.shell(image="alpine:latest"):
            raise ValueError("test error")

        assert cancel_route.called

    @patch("tilde.resources.shell.ws_connect")
    def test_approval_warning(self, mock_ws_connect, mock_api, repo):
        """Shell emits UserWarning when sandbox awaits approval."""
        _create_sandbox_route(mock_api, "sbx-approve")
        mock_api.get(f"{BASE_PATH}/sbx-approve/status").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "status": "running",
                        "exit_code": None,
                        "commit_id": "",
                        "web_url": "",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "status": "awaiting_approval",
                        "exit_code": 0,
                        "commit_id": "",
                        "web_url": "https://app.tilde.run/approve/sbx-approve",
                    },
                ),
            ]
        )

        mock_ws = MagicMock()
        mock_ws_connect.return_value = mock_ws

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with repo.shell(image="alpine:latest"):
                pass
            assert len(w) == 1
            assert "awaiting_approval" not in str(w[0].message)  # URL is in the message
            assert "sbx-approve" in str(w[0].message)

    @patch("tilde.resources.shell.ws_connect")
    def test_sandbox_not_running_raises(self, mock_ws_connect, mock_api, repo):
        """Shell raises SandboxError if sandbox enters terminal state before running."""
        _create_sandbox_route(mock_api, "sbx-dead")
        mock_api.get(f"{BASE_PATH}/sbx-dead/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "failed",
                    "exit_code": 1,
                    "commit_id": "",
                    "web_url": "",
                },
            )
        )

        with pytest.raises(SandboxError, match="terminal state"), repo.shell(image="alpine:latest"):
            pass


class TestShellDefaultImage:
    @patch("tilde.resources.shell.ws_connect")
    def test_uses_default_sandbox_image(self, mock_ws_connect, mock_api):
        """shell() uses the configured default_sandbox_image."""
        from tilde.client import Client

        c = Client(api_key="test-key", default_sandbox_image="myimage:v1")
        r = c.repository("test-org/test-repo")

        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-default"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-default/status").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "status": "running",
                        "exit_code": None,
                        "commit_id": "",
                        "web_url": "",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "status": "committed",
                        "exit_code": 0,
                        "commit_id": "c-x",
                        "web_url": "",
                    },
                ),
            ]
        )

        mock_ws = MagicMock()
        mock_ws_connect.return_value = mock_ws

        with r.shell():
            pass

        import json

        payload = json.loads(route.calls[0].request.content)
        assert payload["image"] == "myimage:v1"
        assert payload["interactive"] is True
        c.close()
