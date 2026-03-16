"""Tests for Sandbox resource."""

import httpx

from tilde.models import SandboxData
from tilde.resources.sandboxes import LogStream, SandboxResource, SandboxStatus

BASE_PATH = "/organizations/test-org/repositories/test-repo/sandboxes"


class TestCreateSandbox:
    def test_create_sandbox_minimal(self, mock_api, repo):
        """POST .../sandboxes with only image creates a sandbox."""
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-123"})
        )
        sandbox = repo.sandbox(image="python:3.10")
        assert isinstance(sandbox, SandboxResource)
        assert sandbox.id == "sbx-123"
        assert route.called
        body = route.calls[0].request.content
        import json

        payload = json.loads(body)
        assert payload == {"image": "python:3.10"}

    def test_create_sandbox_full(self, mock_api, repo):
        """POST .../sandboxes with all options."""
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-456"})
        )
        sandbox = repo.sandbox(
            image="python:3.10",
            command=["python", "script.py"],
            env={"MY_SECRET": "secret_value"},  # pragma: allowlist secret
            mountpoint="/data",
            path_prefix="subdir/",
            timeout_seconds=300,
            run_as={"type": "agent", "id": "00000000-0000-0000-0000-000000000001"},
        )
        assert sandbox.id == "sbx-456"
        import json

        payload = json.loads(route.calls[0].request.content)
        assert payload["image"] == "python:3.10"
        assert payload["command"] == ["python", "script.py"]
        assert payload["env_vars"] == {"MY_SECRET": "secret_value"}  # pragma: allowlist secret
        assert payload["mountpoint"] == "/data"
        assert payload["path_prefix"] == "subdir/"
        assert payload["timeout_seconds"] == 300
        assert payload["run_as"] == {
            "type": "agent",
            "id": "00000000-0000-0000-0000-000000000001",
        }

    def test_create_sandbox_interactive(self, mock_api, repo):
        """POST .../sandboxes with interactive=True includes it in body."""
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-int"})
        )
        from tilde.resources.sandboxes import create_sandbox

        sandbox = create_sandbox(
            repo._client,
            "test-org",
            "test-repo",
            image="python:3.10",
            interactive=True,
        )
        assert sandbox.id == "sbx-int"
        import json

        payload = json.loads(route.calls[0].request.content)
        assert payload["interactive"] is True

    def test_create_sandbox_not_interactive_by_default(self, mock_api, repo):
        """POST .../sandboxes omits interactive when False."""
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-noint"})
        )
        repo.sandbox(image="python:3.10")
        import json

        payload = json.loads(route.calls[0].request.content)
        assert "interactive" not in payload


class TestListSandboxes:
    def test_list_sandboxes(self, mock_api, repo):
        """GET .../sandboxes returns paginated sandbox resources."""
        mock_api.get(BASE_PATH).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "sbx-1", "image": "python:3.10", "status": "running"},
                        {"id": "sbx-2", "image": "node:18", "status": "committed"},
                    ],
                    "pagination": {
                        "has_more": False,
                        "next_offset": None,
                        "max_per_page": 100,
                    },
                },
            )
        )
        sandboxes = list(repo.sandboxes())
        assert len(sandboxes) == 2
        assert all(isinstance(s, SandboxResource) for s in sandboxes)
        assert sandboxes[0].id == "sbx-1"
        assert sandboxes[1].id == "sbx-2"

    def test_list_sandboxes_pagination(self, mock_api, repo):
        """Pagination fetches multiple pages."""
        mock_api.get(BASE_PATH).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "results": [{"id": "sbx-1"}],
                        "pagination": {
                            "has_more": True,
                            "next_offset": "sbx-1",
                            "max_per_page": 1,
                        },
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "results": [{"id": "sbx-2"}],
                        "pagination": {
                            "has_more": False,
                            "next_offset": None,
                            "max_per_page": 1,
                        },
                    },
                ),
            ]
        )
        sandboxes = list(repo.sandboxes())
        assert len(sandboxes) == 2
        assert sandboxes[0].id == "sbx-1"
        assert sandboxes[1].id == "sbx-2"


class TestSandboxStatus:
    def test_status(self, mock_api, repo):
        """GET .../sandboxes/{id}/status returns SandboxStatus."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-st"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-st/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "running",
                    "status_reason": "",
                    "exit_code": None,
                    "commit_id": "",
                    "web_url": "",
                },
            )
        )
        sandbox = repo.sandbox(image="python:3.10")
        status = sandbox.status()
        assert isinstance(status, SandboxStatus)
        assert status.state == "running"
        assert status.exit_code is None

    def test_status_committed(self, mock_api, repo):
        """Status reflects committed state with exit code."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-done"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-done/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "committed",
                    "status_reason": "",
                    "exit_code": 0,
                    "commit_id": "commit-abc",
                    "web_url": "",
                },
            )
        )
        sandbox = repo.sandbox(image="python:3.10")
        status = sandbox.status()
        assert status.state == "committed"
        assert status.exit_code == 0
        assert status.commit_id == "commit-abc"

    def test_status_awaiting_approval(self, mock_api, repo):
        """Status includes web_url when awaiting approval."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-approve"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-approve/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "awaiting_approval",
                    "status_reason": "policy requires approval",
                    "exit_code": 0,
                    "commit_id": "",
                    "web_url": "https://app.tilde.run/approve/sbx-approve",
                },
            )
        )
        sandbox = repo.sandbox(image="python:3.10")
        status = sandbox.status()
        assert status.state == "awaiting_approval"
        assert status.web_url == "https://app.tilde.run/approve/sbx-approve"


class TestSandboxCancel:
    def test_cancel(self, mock_api, repo):
        """DELETE .../sandboxes/{id} cancels the sandbox."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-cancel"})
        )
        cancel_route = mock_api.delete(f"{BASE_PATH}/sbx-cancel").mock(
            return_value=httpx.Response(202, json={"message": "cancellation accepted"})
        )
        sandbox = repo.sandbox(image="python:3.10")
        sandbox.cancel()
        assert cancel_route.called


class TestSandboxLogStreams:
    def test_stdout_returns_log_stream(self, mock_api, repo):
        """status.stdout() returns a LogStream."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-log"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-log/status").mock(
            return_value=httpx.Response(
                200,
                json={"status": "running", "exit_code": None, "commit_id": "", "web_url": ""},
            )
        )
        sandbox = repo.sandbox(image="python:3.10")
        status = sandbox.status()
        stream = status.stdout()
        assert isinstance(stream, LogStream)

    def test_stderr_returns_log_stream(self, mock_api, repo):
        """status.stderr() returns a LogStream."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-log2"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-log2/status").mock(
            return_value=httpx.Response(
                200,
                json={"status": "running", "exit_code": None, "commit_id": "", "web_url": ""},
            )
        )
        sandbox = repo.sandbox(image="python:3.10")
        status = sandbox.status()
        stream = status.stderr()
        assert isinstance(stream, LogStream)

    def test_stdout_stream_lines(self, mock_api, repo):
        """LogStream yields lines from the streaming response."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-stream"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-stream/status").mock(
            return_value=httpx.Response(
                200,
                json={"status": "running", "exit_code": None, "commit_id": "", "web_url": ""},
            )
        )
        mock_api.get(f"{BASE_PATH}/sbx-stream/stdout").mock(
            return_value=httpx.Response(
                200,
                text="line 1\nline 2\nline 3\n",
                headers={"content-type": "text/plain"},
            )
        )
        sandbox = repo.sandbox(image="python:3.10")
        status = sandbox.status()
        with status.stdout() as stream:
            lines = list(stream)
        assert lines == ["line 1", "line 2", "line 3"]

    def test_stderr_stream_lines(self, mock_api, repo):
        """LogStream yields stderr lines from the streaming response."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-err"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-err/status").mock(
            return_value=httpx.Response(
                200,
                json={"status": "failed", "exit_code": 1, "commit_id": "", "web_url": ""},
            )
        )
        mock_api.get(f"{BASE_PATH}/sbx-err/stderr").mock(
            return_value=httpx.Response(
                200,
                text="error: something went wrong\n",
                headers={"content-type": "text/plain"},
            )
        )
        sandbox = repo.sandbox(image="python:3.10")
        status = sandbox.status()
        with status.stderr() as stream:
            lines = list(stream)
        assert lines == ["error: something went wrong"]


class TestSandboxDataModel:
    def test_from_dict(self):
        """SandboxData.from_dict() parses all fields."""
        data = SandboxData.from_dict(
            {
                "id": "sbx-1",
                "repository_id": "repo-1",
                "image": "python:3.10",
                "command": ["python", "run.py"],
                "mountpoint": "/sandbox",
                "path_prefix": "",
                "timeout_seconds": 600,
                "env_vars": {"KEY": "val"},
                "status": "running",
                "status_reason": "",
                "error_message": "",
                "exit_code": None,
                "commit_id": "",
                "web_url": "",
                "created_by_type": "user",
                "created_by": "user-1",
                "created_at": "2026-01-15T10:00:00+00:00",
                "updated_at": "2026-01-15T10:01:00+00:00",
                "finished_at": None,
            }
        )
        assert data.id == "sbx-1"
        assert data.image == "python:3.10"
        assert data.command == ["python", "run.py"]
        assert data.timeout_seconds == 600
        assert data.env_vars == {"KEY": "val"}
        assert data.status == "running"
        assert data.exit_code is None
        assert data.created_at is not None
        assert data.finished_at is None

    def test_from_dict_minimal(self):
        """SandboxData.from_dict() handles empty dict gracefully."""
        data = SandboxData.from_dict({})
        assert data.id == ""
        assert data.command == []
        assert data.env_vars == {}
        assert data.exit_code is None
