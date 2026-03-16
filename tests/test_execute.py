"""Tests for Repository.execute() (non-interactive sandbox)."""

from __future__ import annotations

import json

import httpx
import pytest

from tilde._output_stream import OutputStream
from tilde.exceptions import CommandError
from tilde.models import RunResult

BASE_PATH = "/organizations/test-org/repositories/test-repo/sandboxes"


def _setup_sandbox(mock_api, sandbox_id, status, exit_code=0, stdout="", stderr=""):
    """Set up mock routes for a non-interactive sandbox lifecycle."""
    mock_api.post(BASE_PATH).mock(return_value=httpx.Response(201, json={"sandbox_id": sandbox_id}))
    mock_api.get(f"{BASE_PATH}/{sandbox_id}/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": status,
                "status_reason": "",
                "exit_code": exit_code,
                "commit_id": "c-1" if status == "committed" else "",
                "web_url": "",
            },
        )
    )
    mock_api.get(f"{BASE_PATH}/{sandbox_id}/stdout").mock(
        return_value=httpx.Response(200, text=stdout, headers={"content-type": "text/plain"})
    )
    mock_api.get(f"{BASE_PATH}/{sandbox_id}/stderr").mock(
        return_value=httpx.Response(200, text=stderr, headers={"content-type": "text/plain"})
    )


class TestExecuteBasic:
    def test_string_command(self, mock_api, repo):
        """String command is wrapped in sh -c."""
        route = _setup_sandbox(mock_api, "sbx-str", "committed", stdout="hello\n")
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-str"})
        )

        result = repo.execute("echo hello")

        assert isinstance(result, RunResult)
        assert result.exit_code == 0
        assert isinstance(result.stdout, OutputStream)
        assert "hello" in result.stdout.text()

        payload = json.loads(route.calls[0].request.content)
        assert payload["command"] == ["sh", "-c", "echo hello"]

    def test_list_command(self, mock_api, repo):
        """List command is passed directly."""
        _setup_sandbox(mock_api, "sbx-list", "committed", stdout="ok\n")
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-list"})
        )

        result = repo.execute(["python", "-c", "print('ok')"])

        payload = json.loads(route.calls[0].request.content)
        assert payload["command"] == ["python", "-c", "print('ok')"]
        assert result.exit_code == 0

    def test_captures_stderr(self, mock_api, repo):
        """execute() captures stderr output."""
        _setup_sandbox(
            mock_api,
            "sbx-err",
            "committed",
            exit_code=0,
            stdout="",
            stderr="warning: something\n",
        )

        result = repo.execute("cmd", check=False)
        assert "warning: something" in result.stderr.text()


class TestExecuteCheck:
    def test_check_true_raises_on_failure(self, mock_api, repo):
        """check=True raises CommandError on non-zero exit."""
        _setup_sandbox(mock_api, "sbx-chk", "failed", exit_code=1, stderr="error\n")

        with pytest.raises(CommandError) as exc_info:
            repo.execute("bad_cmd")

        assert exc_info.value.result.exit_code == 1
        assert exc_info.value.command == "bad_cmd"

    def test_check_false_no_raise(self, mock_api, repo):
        """check=False returns result even on failure."""
        _setup_sandbox(mock_api, "sbx-nochk", "failed", exit_code=2)

        result = repo.execute("bad_cmd", check=False)
        assert result.exit_code == 2

    def test_check_true_list_command(self, mock_api, repo):
        """CommandError.command is joined for list commands."""
        _setup_sandbox(mock_api, "sbx-chklist", "failed", exit_code=1)

        with pytest.raises(CommandError) as exc_info:
            repo.execute(["python", "fail.py"])

        assert exc_info.value.command == "python fail.py"


class TestExecuteDefaultImage:
    def test_uses_default_sandbox_image(self, mock_api):
        """execute() uses configured default_sandbox_image."""
        from tilde.client import Client

        c = Client(api_key="test-key", default_sandbox_image="custom:img")
        r = c.repository("test-org/test-repo")

        _setup_sandbox(mock_api, "sbx-dimg", "committed", stdout="ok\n")
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-dimg"})
        )

        r.execute("echo ok")

        payload = json.loads(route.calls[0].request.content)
        assert payload["image"] == "custom:img"
        # Non-interactive: no 'interactive' key
        assert "interactive" not in payload
        c.close()

    def test_image_param_overrides_default(self, mock_api, repo):
        """Explicit image= overrides the default."""
        _setup_sandbox(mock_api, "sbx-ovr", "committed", stdout="ok\n")
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-ovr"})
        )

        repo.execute("echo ok", image="special:v2")

        payload = json.loads(route.calls[0].request.content)
        assert payload["image"] == "special:v2"


class TestExecuteFailedSandbox:
    def test_failed_sandbox_reads_output(self, mock_api, repo):
        """Even when sandbox fails, stdout/stderr are captured."""
        _setup_sandbox(
            mock_api,
            "sbx-fout",
            "failed",
            exit_code=127,
            stdout="partial output\n",
            stderr="command not found\n",
        )

        result = repo.execute("nonexistent", check=False)
        assert result.exit_code == 127
        assert "partial output" in result.stdout.text()
        assert "command not found" in result.stderr.text()
