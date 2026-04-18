"""Tests for Shell (interactive sandbox via WebSocket)."""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tilde._output_stream import OutputStream
from tilde.exceptions import CommandError, SandboxError
from tilde.models import RunResult
from tilde.resources.shell import _FRAME_STDIN, _FRAME_STDOUT

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


def _stdout_frame(text: str) -> bytes:
    """Build a server→client stdout binary frame (0x01 prefix)."""
    return bytes([_FRAME_STDOUT]) + text.encode("utf-8")


def _extract_stdin(mock_ws) -> str:
    """Extract the last stdin payload sent via the binary protocol."""
    raw = mock_ws.send.call_args_list[-1][0][0]
    assert isinstance(raw, bytes)
    assert raw[0] == _FRAME_STDIN
    return raw[1:].decode("utf-8")


def _make_ws_recv(mock_ws, cmd_output=None, exit_code=0):
    """Create a recv side_effect that handles the ready probe and optionally a run() call.

    The ready probe (with ``stty`` + ``echo``) is sent during ``__enter__``.
    After the ready marker is found, a drain phase reads with short timeout —
    the side_effect raises ``TimeoutError`` for those calls to terminate the drain.
    If *cmd_output* is not None, the next recv handles the run() markers.
    """
    ready_found = {"done": False}

    def recv_side_effect(timeout=None):
        sent_raw = mock_ws.send.call_args_list[-1][0][0]
        assert isinstance(sent_raw, bytes) and sent_raw[0] == _FRAME_STDIN
        sent = sent_raw[1:].decode("utf-8")

        # Handle ready probe (stty + echo)
        if "__TILDE_READY_" in sent and not ready_found["done"]:
            ready_found["done"] = True
            start = sent.index("__TILDE_READY_")
            end = sent.index("__", start + len("__TILDE_READY_")) + 2
            marker = sent[start:end]
            return _stdout_frame(f"$ {sent}{marker}\r\n")

        # Drain phase — short timeout calls after the ready marker
        if ready_found["done"] and "__TILDE_BEGIN_" not in sent:
            raise TimeoutError

        # Handle run() command markers
        if "__TILDE_BEGIN_" in sent:
            begin_idx = sent.index("__TILDE_BEGIN_") + len("__TILDE_BEGIN_")
            end_idx = sent.index("__", begin_idx)
            marker = sent[begin_idx:end_idx]
            begin_m = f"__TILDE_BEGIN_{marker}__"
            end_m = f"__TILDE_END_{marker}__"
            output = cmd_output if cmd_output is not None else ""
            return _stdout_frame(f"{output}\r\n{begin_m}\r\n{exit_code}\r\n{end_m}\r\n")

        return _stdout_frame("")

    return recv_side_effect


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
        mock_ws.recv.side_effect = _make_ws_recv(mock_ws, "hello world")

        with repo.shell(image="alpine") as sh:
            result = sh.run("echo hello world")

        assert isinstance(result, RunResult)
        assert result.exit_code == 0
        assert isinstance(result.stdout, OutputStream)
        assert "hello world" in result.stdout.text()

    @patch("tilde.resources.shell.ws_connect")
    def test_sends_binary_stdin_frames(self, mock_ws_connect, mock_api, repo):
        """All sends use binary frames with 0x00 stdin prefix."""
        _create_sandbox_route(mock_api, "sbx-bin")
        mock_api.get(f"{BASE_PATH}/sbx-bin/status").mock(
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
                        "commit_id": "c-bin",
                        "web_url": "",
                    },
                ),
            ]
        )

        mock_ws = MagicMock()
        mock_ws_connect.return_value = mock_ws
        mock_ws.recv.side_effect = _make_ws_recv(mock_ws, "ok")

        with repo.shell(image="alpine") as sh:
            sh.run("echo ok")

        # Every send call should be bytes starting with 0x00
        for call in mock_ws.send.call_args_list:
            data = call[0][0]
            assert isinstance(data, bytes), f"Expected bytes, got {type(data)}"
            assert data[0] == _FRAME_STDIN, f"Expected stdin prefix 0x00, got 0x{data[0]:02x}"

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
        mock_ws.recv.side_effect = _make_ws_recv(mock_ws, "error output", exit_code=1)

        with repo.shell(image="alpine") as sh:
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
        mock_ws.recv.side_effect = _make_ws_recv(mock_ws, exit_code=42)

        with repo.shell(image="alpine") as sh:
            result = sh.run("exit 42")
        assert result.exit_code == 42

    @patch("tilde.resources.shell.ws_connect")
    def test_run_strips_ansi_escape_codes(self, mock_ws_connect, mock_api, repo):
        """run() strips ANSI escape codes from command output."""
        _create_sandbox_route(mock_api, "sbx-ansi")
        mock_api.get(f"{BASE_PATH}/sbx-ansi/status").mock(
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
                        "commit_id": "c-ansi",
                        "web_url": "",
                    },
                ),
            ]
        )

        mock_ws = MagicMock()
        mock_ws_connect.return_value = mock_ws
        # Simulate output with ANSI color codes (e.g. colored ls output)
        colored_output = "\x1b[1;34mdir1\x1b[0m  \x1b[0;32mfile.txt\x1b[0m"
        mock_ws.recv.side_effect = _make_ws_recv(mock_ws, colored_output)

        with repo.shell(image="alpine") as sh:
            result = sh.run("ls --color=always")

        assert "\x1b" not in result.stdout.text()
        assert "dir1" in result.stdout.text()
        assert "file.txt" in result.stdout.text()


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
        mock_ws.recv.side_effect = _make_ws_recv(mock_ws)

        with pytest.raises(ValueError, match="test error"), repo.shell(image="alpine"):
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
        mock_ws.recv.side_effect = _make_ws_recv(mock_ws)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with repo.shell(image="alpine"):
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

        with pytest.raises(SandboxError, match="terminal state"), repo.shell(image="alpine"):
            pass


class TestShellDefaultImage:
    @patch("tilde.resources.shell.ws_connect")
    def test_uses_default_sandbox_image(self, mock_ws_connect, mock_api):
        """shell() uses the configured default_sandbox_image."""
        from tilde.client import Client

        c = Client(api_key="test-key", default_sandbox_image="myimage")
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
        mock_ws.recv.side_effect = _make_ws_recv(mock_ws)

        with r.shell():
            pass

        import json

        payload = json.loads(route.calls[0].request.content)
        assert payload["image"] == "myimage"
        assert payload["interactive"] is True
        c.close()
