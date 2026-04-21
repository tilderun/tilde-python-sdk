"""Tests for Shell (per-call /exec WebSocket against a running sandbox)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tilde._output_stream import OutputStream
from tilde.exceptions import CommandError, SandboxError
from tilde.models import RunResult
from tilde.resources.shell import (
    _FRAME_EXIT,
    _FRAME_LAUNCH,
    _FRAME_STDERR,
    _FRAME_STDIN,
    _FRAME_STDIN_CLOSE,
    _FRAME_STDOUT,
)

BASE_PATH = "/organizations/test-org/repositories/test-repo/sandboxes"


# -- HTTP fixtures ----------------------------------------------------------


def _create_sandbox_route(mock_api, sandbox_id="sbx-shell"):
    return mock_api.post(BASE_PATH).mock(
        return_value=httpx.Response(201, json={"sandbox_id": sandbox_id})
    )


def _running_status(mock_api, sandbox_id):
    """Status endpoint always reports ``running`` — good enough for __enter__."""
    mock_api.get(f"{BASE_PATH}/{sandbox_id}/status").mock(
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


def _cancel_route(mock_api, sandbox_id):
    return mock_api.delete(f"{BASE_PATH}/{sandbox_id}").mock(
        return_value=httpx.Response(202, json={"message": "cancelled"})
    )


def _finish_route(mock_api, sandbox_id):
    return mock_api.post(f"{BASE_PATH}/{sandbox_id}/finish").mock(
        return_value=httpx.Response(202, json={"message": "finishing"})
    )


def _bootstrap(mock_api, sandbox_id):
    """Register all routes a successful ``with repo.shell(): ...`` needs.

    Clean exits take the commit path via ``/finish``; exceptional exits
    fall through to ``cancel`` (``DELETE``), so we wire both.
    """
    _create_sandbox_route(mock_api, sandbox_id)
    _running_status(mock_api, sandbox_id)
    _cancel_route(mock_api, sandbox_id)
    return _finish_route(mock_api, sandbox_id)


# -- WebSocket mocks --------------------------------------------------------


def _exec_frame(frame_type: int, payload: bytes = b"") -> bytes:
    return bytes([frame_type]) + payload


def _stage_exec_reply(
    stdout: bytes = b"",
    stderr: bytes = b"",
    exit_code: int = 0,
) -> list[bytes]:
    frames: list[bytes] = []
    if stdout:
        frames.append(_exec_frame(_FRAME_STDOUT, stdout))
    if stderr:
        frames.append(_exec_frame(_FRAME_STDERR, stderr))
    frames.append(_exec_frame(_FRAME_EXIT, json.dumps({"exit_code": exit_code}).encode("utf-8")))
    return frames


def _make_recv(frames):
    remaining = list(frames)

    def recv(timeout=None):
        if not remaining:
            raise TimeoutError
        return remaining.pop(0)

    return recv


def _make_ws_connect(exec_replies):
    """Build a ws_connect side_effect that dispenses one exec mock per /exec call.

    ``exec_replies`` is a list of tuples ``(stdout, stderr, exit_code)``, one
    per expected ``sh.run()`` call.  Any other WebSocket URL raises.
    """
    exec_conns: list[MagicMock] = []
    idx = [0]

    def connect(url, **kwargs):
        if "/exec" in url:
            i = idx[0]
            idx[0] += 1
            if i >= len(exec_replies):
                raise AssertionError(f"Unexpected /exec call #{i + 1} ({url})")
            frames = _stage_exec_reply(*exec_replies[i])
            ws = MagicMock()
            ws.recv = _make_recv(frames)
            exec_conns.append(ws)
            return ws
        raise AssertionError(f"Unexpected WS URL: {url}")

    connect.exec_conns = exec_conns  # type: ignore[attr-defined]
    return connect


def _decode_launch(ws_send_mock) -> dict:
    first = ws_send_mock.call_args_list[0][0][0]
    assert isinstance(first, bytes)
    assert first[0] == _FRAME_LAUNCH
    return json.loads(first[1:].decode("utf-8"))


# -- Tests ------------------------------------------------------------------


class TestShellRun:
    @patch("tilde.resources.shell.ws_connect")
    def test_run_captures_stdout_and_exit_code(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-run")
        mock_ws_connect.side_effect = _make_ws_connect([(b"hello world\n", b"", 0)])

        with repo.shell(image="python:3.12") as sh:
            result = sh.run("echo hello world")

        assert isinstance(result, RunResult)
        assert result.exit_code == 0
        assert isinstance(result.stdout, OutputStream)
        assert result.stdout.text() == "hello world\n"
        assert result.stderr.text() == ""

    @patch("tilde.resources.shell.ws_connect")
    def test_run_captures_stderr_separately(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-err")
        mock_ws_connect.side_effect = _make_ws_connect([(b"out\n", b"err\n", 3)])

        with repo.shell(image="python:3.12") as sh:
            result = sh.run("printf out; printf err >&2; exit 3")

        assert result.stdout.text() == "out\n"
        assert result.stderr.text() == "err\n"
        assert result.exit_code == 3

    @patch("tilde.resources.shell.ws_connect")
    def test_run_check_raises_on_nonzero(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-fail")
        mock_ws_connect.side_effect = _make_ws_connect([(b"", b"boom\n", 1)])

        with repo.shell(image="python:3.12") as sh:
            with pytest.raises(CommandError) as exc_info:
                sh.run("false", check=True)
            assert exc_info.value.result.exit_code == 1
            assert exc_info.value.result.stderr.text() == "boom\n"
            assert exc_info.value.command == "false"

    @patch("tilde.resources.shell.ws_connect")
    def test_run_check_false_no_raise(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-nocheck")
        mock_ws_connect.side_effect = _make_ws_connect([(b"", b"", 42)])

        with repo.shell(image="python:3.12") as sh:
            result = sh.run("exit 42")
        assert result.exit_code == 42

    @patch("tilde.resources.shell.ws_connect")
    def test_run_preserves_bytes_verbatim(self, mock_ws_connect, mock_api, repo):
        """The SDK does no ANSI stripping, no CRLF normalization — byte-for-byte."""
        _bootstrap(mock_api, "sbx-raw")
        raw = b"\x1b[1;34mdir1\x1b[0m\r\nfile.txt\r\n"
        mock_ws_connect.side_effect = _make_ws_connect([(raw, b"", 0)])

        with repo.shell(image="python:3.12") as sh:
            result = sh.run("ls --color=always")
        assert result.stdout.read() == raw

    @patch("tilde.resources.shell.ws_connect")
    def test_run_wraps_string_cmd_in_sh_c(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-str")
        connector = _make_ws_connect([(b"", b"", 0)])
        mock_ws_connect.side_effect = connector

        with repo.shell(image="python:3.12") as sh:
            sh.run("echo one && echo two")

        launch = _decode_launch(connector.exec_conns[0].send)
        assert launch["cmd"] == ["sh", "-c", "echo one && echo two"]

    @patch("tilde.resources.shell.ws_connect")
    def test_run_list_cmd_bypasses_shell(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-list")
        connector = _make_ws_connect([(b"", b"", 0)])
        mock_ws_connect.side_effect = connector

        with repo.shell(image="python:3.12") as sh:
            sh.run(["/bin/ls", "-l", "/tmp"])

        launch = _decode_launch(connector.exec_conns[0].send)
        assert launch["cmd"] == ["/bin/ls", "-l", "/tmp"]
        assert "env" not in launch
        assert "cwd" not in launch

    @patch("tilde.resources.shell.ws_connect")
    def test_run_forwards_env_and_cwd(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-env")
        connector = _make_ws_connect([(b"", b"", 0)])
        mock_ws_connect.side_effect = connector

        with repo.shell(image="python:3.12") as sh:
            sh.run("pwd", env={"FOO": "bar"}, cwd="/sandbox/sub")

        launch = _decode_launch(connector.exec_conns[0].send)
        assert launch["env"] == {"FOO": "bar"}
        assert launch["cwd"] == "/sandbox/sub"

    @patch("tilde.resources.shell.ws_connect")
    def test_run_sends_stdin_then_closes(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-stdin")
        connector = _make_ws_connect([(b"hello\n", b"", 0)])
        mock_ws_connect.side_effect = connector

        with repo.shell(image="python:3.12") as sh:
            result = sh.run("cat", stdin=b"hello\n")

        assert result.stdout.text() == "hello\n"
        sends = connector.exec_conns[0].send.call_args_list
        assert sends[0][0][0][0] == _FRAME_LAUNCH
        assert sends[1][0][0] == bytes([_FRAME_STDIN]) + b"hello\n"
        assert sends[2][0][0] == bytes([_FRAME_STDIN_CLOSE])

    @patch("tilde.resources.shell.ws_connect")
    def test_multiple_runs_use_independent_ws_connections(self, mock_ws_connect, mock_api, repo):
        _bootstrap(mock_api, "sbx-multi")
        connector = _make_ws_connect([(b"first\n", b"", 0), (b"", b"second\n", 2)])
        mock_ws_connect.side_effect = connector

        with repo.shell(image="python:3.12") as sh:
            r1 = sh.run("echo first")
            r2 = sh.run("echo second >&2; exit 2")

        assert r1.stdout.text() == "first\n"
        assert r1.exit_code == 0
        assert r2.stderr.text() == "second\n"
        assert r2.exit_code == 2
        assert len(connector.exec_conns) == 2
        assert connector.exec_conns[0].close.called
        assert connector.exec_conns[1].close.called

    @patch("tilde.resources.shell.ws_connect")
    def test_no_shell_chrome_bytes_on_the_wire(self, mock_ws_connect, mock_api, repo):
        """No `__TILDE*` markers, no prompt-probing bytes, no TTY setup."""
        _bootstrap(mock_api, "sbx-clean")
        connector = _make_ws_connect([(b"hi\n", b"", 0)])
        mock_ws_connect.side_effect = connector

        with repo.shell(image="python:3.12") as sh:
            sh.run("echo hi")

        for ws in connector.exec_conns:
            for call in ws.send.call_args_list:
                data = call[0][0]
                tail = data[1:].decode("utf-8", errors="replace")
                assert "__TILDE" not in tail
                assert "stty" not in tail


class TestShellLifecycle:
    @patch("tilde.resources.shell.ws_connect")
    def test_clean_exit_finishes_sandbox(self, mock_ws_connect, mock_api, repo):
        """A ``with`` block exiting normally takes the commit path via ``/finish``."""
        _create_sandbox_route(mock_api, "sbx-clean-exit")
        _running_status(mock_api, "sbx-clean-exit")
        cancel = _cancel_route(mock_api, "sbx-clean-exit")
        finish = _finish_route(mock_api, "sbx-clean-exit")
        mock_ws_connect.side_effect = _make_ws_connect([])

        with repo.shell(image="python:3.12"):
            pass

        assert finish.called
        assert not cancel.called

    @patch("tilde.resources.shell.ws_connect")
    def test_exception_cancels_sandbox(self, mock_ws_connect, mock_api, repo):
        """An exception inside the ``with`` block rolls back via ``DELETE``."""
        _create_sandbox_route(mock_api, "sbx-exc")
        _running_status(mock_api, "sbx-exc")
        cancel = _cancel_route(mock_api, "sbx-exc")
        finish = _finish_route(mock_api, "sbx-exc")
        mock_ws_connect.side_effect = _make_ws_connect([])

        with pytest.raises(ValueError, match="boom"), repo.shell(image="python:3.12"):
            raise ValueError("boom")

        assert cancel.called
        assert not finish.called

    @patch("tilde.resources.shell.ws_connect")
    def test_shell_does_not_touch_terminal_ws(self, mock_ws_connect, mock_api, repo):
        """The SDK must never open /terminal; /exec is the only channel used."""
        _create_sandbox_route(mock_api, "sbx-no-term")
        _running_status(mock_api, "sbx-no-term")
        _cancel_route(mock_api, "sbx-no-term")
        _finish_route(mock_api, "sbx-no-term")
        mock_ws_connect.side_effect = _make_ws_connect([])

        with repo.shell(image="python:3.12"):
            pass

        for call in mock_ws_connect.call_args_list:
            url = call[0][0]
            assert "/terminal" not in url

    @patch("tilde.resources.shell.ws_connect")
    def test_sandbox_not_running_raises(self, mock_ws_connect, mock_api, repo):
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

        with pytest.raises(SandboxError, match="terminal state"), repo.shell(image="python:3.12"):
            pass


class TestShellSandboxCreation:
    @patch("tilde.resources.shell.ws_connect")
    def test_creates_service_sandbox(self, mock_ws_connect, mock_api, repo):
        """``repo.shell()`` creates a ``mode: "service"`` sandbox with no command."""
        route = _create_sandbox_route(mock_api, "sbx-plain")
        _running_status(mock_api, "sbx-plain")
        _cancel_route(mock_api, "sbx-plain")
        _finish_route(mock_api, "sbx-plain")
        mock_ws_connect.side_effect = _make_ws_connect([])

        with repo.shell(image="python:3.12"):
            pass

        payload = json.loads(route.calls[0].request.content)
        assert payload["image"] == "python:3.12"
        assert payload["mode"] == "service"
        assert "interactive" not in payload
        assert "command" not in payload

    @patch("tilde.resources.shell.ws_connect")
    def test_uses_default_sandbox_image(self, mock_ws_connect, mock_api):
        from tilde.client import Client

        c = Client(api_key="test-key", default_sandbox_image="myimage")
        r = c.repository("test-org/test-repo")

        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-default"})
        )
        _running_status(mock_api, "sbx-default")
        _cancel_route(mock_api, "sbx-default")
        _finish_route(mock_api, "sbx-default")
        mock_ws_connect.side_effect = _make_ws_connect([])

        with r.shell():
            pass

        payload = json.loads(route.calls[0].request.content)
        assert payload["image"] == "myimage"
        assert payload["mode"] == "service"
        c.close()
