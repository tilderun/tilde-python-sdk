"""Tests for Sandbox and Sandboxes."""

import httpx

from tilde.models import LogStream, Sandbox, SandboxStatus

BASE_PATH = "/organizations/test-org/repositories/test-repo/sandboxes"


class TestCreateSandbox:
    def test_create_minimal(self, mock_api, repo):
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-123"})
        )
        sandbox = repo.sandboxes.create(image="python-310")
        assert isinstance(sandbox, Sandbox)
        assert sandbox.id == "sbx-123"
        assert route.called
        import json

        payload = json.loads(route.calls[0].request.content)
        assert payload == {"image": "python-310"}

    def test_create_full(self, mock_api, repo):
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-456"})
        )
        sandbox = repo.sandboxes.create(
            image="python-310",
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
        assert payload["image"] == "python-310"
        assert payload["command"] == ["python", "script.py"]
        assert payload["env_vars"] == {"MY_SECRET": "secret_value"}  # pragma: allowlist secret
        assert payload["mountpoint"] == "/data"
        assert payload["path_prefix"] == "subdir/"
        assert payload["timeout_seconds"] == 300
        assert payload["run_as"] == {
            "type": "agent",
            "id": "00000000-0000-0000-0000-000000000001",
        }

    def test_not_interactive_by_default(self, mock_api, repo):
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-noint"})
        )
        repo.sandboxes.create(image="python-310")
        import json

        payload = json.loads(route.calls[0].request.content)
        assert "interactive" not in payload


class TestListSandboxes:
    def test_list(self, mock_api, repo):
        mock_api.get(BASE_PATH).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "sbx-1", "image": "python-310", "status": "running"},
                        {"id": "sbx-2", "image": "node-18", "status": "done"},
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        sandboxes = list(repo.sandboxes.list())
        assert len(sandboxes) == 2
        assert all(isinstance(s, Sandbox) for s in sandboxes)
        assert sandboxes[0].id == "sbx-1"
        assert sandboxes[1].id == "sbx-2"

    def test_pagination(self, mock_api, repo):
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
        sandboxes = list(repo.sandboxes.list())
        assert len(sandboxes) == 2


class TestSandboxStatus:
    def test_status_running(self, mock_api, repo):
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
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        assert isinstance(status, SandboxStatus)
        assert status.state == "running"
        assert status.exit_code is None

    def test_status_committed(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-done"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-done/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "done",
                    "status_reason": "committed",
                    "exit_code": 0,
                    "commit_id": "commit-abc",
                    "web_url": "",
                },
            )
        )
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        assert status.state == "done"
        assert status.status_reason == "committed"
        assert status.is_terminal is True
        assert status.is_active is False
        assert status.is_committed is True
        assert status.is_awaiting_approval is False
        assert status.has_no_changes is False
        assert status.exit_code == 0
        assert status.commit_id == "commit-abc"

    def test_status_awaiting_approval(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-appr"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-appr/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "done",
                    "status_reason": "awaiting_approval",
                    "exit_code": 0,
                    "commit_id": "",
                    "web_url": "https://tilde.example/approve/123",
                },
            )
        )
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        assert status.state == "done"
        assert status.status_reason == "awaiting_approval"
        assert status.is_awaiting_approval is True
        assert status.is_committed is False
        assert status.is_terminal is True
        assert status.web_url == "https://tilde.example/approve/123"

    def test_status_no_changes(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-noop"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-noop/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "done",
                    "status_reason": "no_changes",
                    "exit_code": 0,
                    "commit_id": "",
                    "web_url": "",
                },
            )
        )
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        assert status.state == "done"
        assert status.status_reason == "no_changes"
        assert status.has_no_changes is True
        assert status.is_committed is False
        assert status.is_terminal is True

    def test_status_errored(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-err"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-err/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "errored",
                    "status_reason": "exit_non_zero",
                    "exit_code": 1,
                    "commit_id": "",
                    "web_url": "",
                    "error_message": "command exited with code 1",
                },
            )
        )
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        assert status.state == "errored"
        assert status.status_reason == "exit_non_zero"
        assert status.is_terminal is True
        assert status.is_active is False
        assert status.exit_code == 1

    def test_status_failed(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-fail"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-fail/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "failed",
                    "status_reason": "internal_error",
                    "exit_code": None,
                    "commit_id": "",
                    "web_url": "",
                    "error_message": "pod terminated unexpectedly",
                },
            )
        )
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        assert status.state == "failed"
        assert status.status_reason == "internal_error"
        assert status.is_terminal is True
        assert status.error_message == "pod terminated unexpectedly"

    def test_status_starting_is_active(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-init"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-init/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "starting",
                    "status_reason": "initializing",
                    "exit_code": None,
                    "commit_id": "",
                    "web_url": "",
                },
            )
        )
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        assert status.state == "starting"
        assert status.status_reason == "initializing"
        assert status.is_active is True
        assert status.is_terminal is False


class TestSandboxCancel:
    def test_cancel(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-cancel"})
        )
        route = mock_api.delete(f"{BASE_PATH}/sbx-cancel").mock(
            return_value=httpx.Response(202, json={"message": "cancellation accepted"})
        )
        sandbox = repo.sandboxes.create(image="python-310")
        sandbox.cancel()
        assert route.called


class TestLogStreams:
    def test_stdout_stream_lines(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-stream"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-stream/status").mock(
            return_value=httpx.Response(
                200,
                json={"status": "running", "exit_code": None, "commit_id": "", "web_url": ""},
            )
        )
        mock_api.get(f"{BASE_PATH}/sbx-stream/logs/stdout").mock(
            return_value=httpx.Response(
                200,
                text="line 1\nerror: boom\nline 3\n",
                headers={"content-type": "text/plain"},
            )
        )
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        stream = status.stdout()
        assert isinstance(stream, LogStream)
        with stream as s:
            lines = list(s)
        assert lines == ["line 1", "error: boom", "line 3"]

    def test_network_stream_lines(self, mock_api, repo):
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json={"sandbox_id": "sbx-netlog"})
        )
        mock_api.get(f"{BASE_PATH}/sbx-netlog/status").mock(
            return_value=httpx.Response(
                200,
                json={"status": "running", "exit_code": None, "commit_id": "", "web_url": ""},
            )
        )
        mock_api.get(f"{BASE_PATH}/sbx-netlog/logs/network").mock(
            return_value=httpx.Response(
                200,
                text='{"decision":"allow","url":"https://a"}\n{"decision":"deny","url":"https://b"}\n',
                headers={"content-type": "application/x-ndjson"},
            )
        )
        sandbox = repo.sandboxes.create(image="python-310")
        status = sandbox.status()
        with status.network() as stream:
            lines = list(stream)
        assert lines == [
            '{"decision":"allow","url":"https://a"}',
            '{"decision":"deny","url":"https://b"}',
        ]
