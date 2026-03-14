"""Tests for Sandbox Trigger resource."""

import json

import httpx

from tilde.models import (
    SandboxTriggerCondition,
    SandboxTriggerConfig,
    SandboxTriggerData,
    SandboxTriggerRunData,
)
from tilde.resources.sandbox_triggers import SandboxTriggerResource

BASE_PATH = "/organizations/test-org/repositories/test-repo/sandbox-triggers"

TRIGGER_RESPONSE = {
    "id": "trig-1",
    "repository_id": "repo-1",
    "name": "validate",
    "description": "Run validation",
    "enabled": True,
    "conditions": [
        {"type": "prefix", "prefix": "data/", "diff_type": "added"},
    ],
    "sandbox_config": {
        "image": "python:3.10",
        "command": ["python", "validate.py"],
        "mountpoint": "/sandbox",
        "path_prefix": "",
        "timeout_seconds": 300,
        "env_vars": {"MODE": "strict"},
    },
    "run_as": None,
    "created_by": "user-1",
    "created_at": "2026-01-15T10:00:00+00:00",
    "updated_at": "2026-01-15T10:01:00+00:00",
}


class TestSandboxTriggerDataModel:
    def test_from_dict(self):
        """SandboxTriggerData.from_dict() parses all fields including nested."""
        data = SandboxTriggerData.from_dict(TRIGGER_RESPONSE)
        assert data.id == "trig-1"
        assert data.name == "validate"
        assert data.enabled is True
        assert len(data.conditions) == 1
        assert isinstance(data.conditions[0], SandboxTriggerCondition)
        assert data.conditions[0].type == "prefix"
        assert data.conditions[0].prefix == "data/"
        assert data.conditions[0].diff_type == "added"
        assert data.sandbox_config is not None
        assert isinstance(data.sandbox_config, SandboxTriggerConfig)
        assert data.sandbox_config.image == "python:3.10"
        assert data.sandbox_config.command == ["python", "validate.py"]
        assert data.sandbox_config.timeout_seconds == 300
        assert data.sandbox_config.env_vars == {"MODE": "strict"}
        assert data.run_as is None
        assert data.created_at is not None

    def test_from_dict_minimal(self):
        """SandboxTriggerData.from_dict() handles empty dict gracefully."""
        data = SandboxTriggerData.from_dict({})
        assert data.id == ""
        assert data.conditions == []
        assert data.sandbox_config is None
        assert data.enabled is False

    def test_condition_from_dict(self):
        """SandboxTriggerCondition.from_dict() parses fields."""
        cond = SandboxTriggerCondition.from_dict(
            {"type": "path_exact", "path": "config.yaml", "diff_type": "modified"}
        )
        assert cond.type == "path_exact"
        assert cond.path == "config.yaml"
        assert cond.diff_type == "modified"

    def test_config_from_dict(self):
        """SandboxTriggerConfig.from_dict() parses fields."""
        cfg = SandboxTriggerConfig.from_dict({"image": "node:18", "command": ["npm", "test"]})
        assert cfg.image == "node:18"
        assert cfg.command == ["npm", "test"]
        assert cfg.timeout_seconds is None


class TestSandboxTriggerRunDataModel:
    def test_from_dict(self):
        """SandboxTriggerRunData.from_dict() parses all fields."""
        data = SandboxTriggerRunData.from_dict(
            {
                "id": "run-1",
                "repository_id": "repo-1",
                "trigger_id": "trig-1",
                "commit_id": "commit-abc",
                "status": "completed",
                "reason": "prefix match",
                "sandbox_id": "sbx-99",
                "matched_paths": ["data/file1.csv", "data/file2.csv"],
                "created_at": "2026-01-15T10:05:00+00:00",
                "updated_at": "2026-01-15T10:06:00+00:00",
            }
        )
        assert data.id == "run-1"
        assert data.trigger_id == "trig-1"
        assert data.status == "completed"
        assert data.sandbox_id == "sbx-99"
        assert data.matched_paths == ["data/file1.csv", "data/file2.csv"]

    def test_from_dict_minimal(self):
        """SandboxTriggerRunData.from_dict() handles empty dict."""
        data = SandboxTriggerRunData.from_dict({})
        assert data.id == ""
        assert data.sandbox_id is None
        assert data.matched_paths == []


class TestCreateSandboxTrigger:
    def test_create_trigger(self, mock_api, repo):
        """POST .../sandbox-triggers creates a trigger."""
        route = mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(201, json=TRIGGER_RESPONSE)
        )
        trigger = repo.sandbox_trigger(
            name="validate",
            conditions=[{"type": "prefix", "prefix": "data/", "diff_type": "added"}],
            sandbox_config={"image": "python:3.10", "command": ["python", "validate.py"]},
            description="Run validation",
        )
        assert isinstance(trigger, SandboxTriggerResource)
        assert trigger.id == "trig-1"
        assert route.called
        payload = json.loads(route.calls[0].request.content)
        assert payload["name"] == "validate"
        assert payload["conditions"] == [
            {"type": "prefix", "prefix": "data/", "diff_type": "added"}
        ]
        assert payload["sandbox_config"]["image"] == "python:3.10"
        assert payload["description"] == "Run validation"

    def test_create_trigger_minimal(self, mock_api, repo):
        """POST .../sandbox-triggers with minimal params."""
        mock_api.post(BASE_PATH).mock(
            return_value=httpx.Response(
                201, json={"id": "trig-2", "name": "minimal", "enabled": True}
            )
        )
        trigger = repo.sandbox_trigger(
            name="minimal",
            conditions=[],
            sandbox_config={"image": "python:3.10"},
        )
        assert trigger.id == "trig-2"


class TestListSandboxTriggers:
    def test_list_triggers(self, mock_api, repo):
        """GET .../sandbox-triggers returns paginated trigger resources."""
        mock_api.get(BASE_PATH).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "trig-1", "name": "validate"},
                        {"id": "trig-2", "name": "lint"},
                    ],
                    "pagination": {
                        "has_more": False,
                        "next_offset": None,
                        "max_per_page": 100,
                    },
                },
            )
        )
        triggers = list(repo.sandbox_triggers())
        assert len(triggers) == 2
        assert all(isinstance(t, SandboxTriggerResource) for t in triggers)
        assert triggers[0].id == "trig-1"
        assert triggers[1].id == "trig-2"

    def test_list_triggers_pagination(self, mock_api, repo):
        """Pagination fetches multiple pages."""
        mock_api.get(BASE_PATH).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "results": [{"id": "trig-1"}],
                        "pagination": {
                            "has_more": True,
                            "next_offset": "trig-1",
                            "max_per_page": 1,
                        },
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "results": [{"id": "trig-2"}],
                        "pagination": {
                            "has_more": False,
                            "next_offset": None,
                            "max_per_page": 1,
                        },
                    },
                ),
            ]
        )
        triggers = list(repo.sandbox_triggers())
        assert len(triggers) == 2
        assert triggers[0].id == "trig-1"
        assert triggers[1].id == "trig-2"


class TestSandboxTriggerGet:
    def test_get(self, mock_api, repo):
        """GET .../sandbox-triggers/{id} returns SandboxTriggerData."""
        mock_api.post(BASE_PATH).mock(return_value=httpx.Response(201, json=TRIGGER_RESPONSE))
        mock_api.get(f"{BASE_PATH}/trig-1").mock(
            return_value=httpx.Response(200, json=TRIGGER_RESPONSE)
        )
        trigger = repo.sandbox_trigger(
            name="validate",
            conditions=[],
            sandbox_config={"image": "python:3.10"},
        )
        data = trigger.get()
        assert isinstance(data, SandboxTriggerData)
        assert data.id == "trig-1"
        assert data.name == "validate"


class TestSandboxTriggerUpdate:
    def test_update(self, mock_api, repo):
        """PUT .../sandbox-triggers/{id} updates the trigger."""
        mock_api.post(BASE_PATH).mock(return_value=httpx.Response(201, json=TRIGGER_RESPONSE))
        updated = {**TRIGGER_RESPONSE, "name": "updated-name"}
        route = mock_api.put(f"{BASE_PATH}/trig-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        trigger = repo.sandbox_trigger(
            name="validate",
            conditions=[],
            sandbox_config={"image": "python:3.10"},
        )
        data = trigger.update(name="updated-name")
        assert isinstance(data, SandboxTriggerData)
        assert data.name == "updated-name"
        assert route.called
        payload = json.loads(route.calls[0].request.content)
        assert payload["name"] == "updated-name"


class TestSandboxTriggerToggle:
    def test_toggle(self, mock_api, repo):
        """PATCH .../sandbox-triggers/{id} toggles enabled."""
        mock_api.post(BASE_PATH).mock(return_value=httpx.Response(201, json=TRIGGER_RESPONSE))
        toggled = {**TRIGGER_RESPONSE, "enabled": False}
        route = mock_api.patch(f"{BASE_PATH}/trig-1").mock(
            return_value=httpx.Response(200, json=toggled)
        )
        trigger = repo.sandbox_trigger(
            name="validate",
            conditions=[],
            sandbox_config={"image": "python:3.10"},
        )
        data = trigger.toggle(enabled=False)
        assert isinstance(data, SandboxTriggerData)
        assert data.enabled is False
        assert route.called
        payload = json.loads(route.calls[0].request.content)
        assert payload == {"enabled": False}


class TestSandboxTriggerDelete:
    def test_delete(self, mock_api, repo):
        """DELETE .../sandbox-triggers/{id} deletes the trigger."""
        mock_api.post(BASE_PATH).mock(return_value=httpx.Response(201, json=TRIGGER_RESPONSE))
        delete_route = mock_api.delete(f"{BASE_PATH}/trig-1").mock(return_value=httpx.Response(204))
        trigger = repo.sandbox_trigger(
            name="validate",
            conditions=[],
            sandbox_config={"image": "python:3.10"},
        )
        trigger.delete()
        assert delete_route.called


class TestSandboxTriggerRuns:
    def test_runs(self, mock_api, repo):
        """GET .../sandbox-triggers/{id}/runs returns paginated runs."""
        mock_api.post(BASE_PATH).mock(return_value=httpx.Response(201, json=TRIGGER_RESPONSE))
        mock_api.get(f"{BASE_PATH}/trig-1/runs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "run-1",
                            "trigger_id": "trig-1",
                            "commit_id": "commit-abc",
                            "status": "completed",
                            "reason": "prefix match",
                            "sandbox_id": "sbx-99",
                            "matched_paths": ["data/file1.csv"],
                        },
                    ],
                    "pagination": {
                        "has_more": False,
                        "next_offset": None,
                        "max_per_page": 100,
                    },
                },
            )
        )
        trigger = repo.sandbox_trigger(
            name="validate",
            conditions=[],
            sandbox_config={"image": "python:3.10"},
        )
        runs = list(trigger.runs())
        assert len(runs) == 1
        assert isinstance(runs[0], SandboxTriggerRunData)
        assert runs[0].id == "run-1"
        assert runs[0].status == "completed"

    def test_runs_pagination(self, mock_api, repo):
        """Runs pagination fetches multiple pages."""
        mock_api.post(BASE_PATH).mock(return_value=httpx.Response(201, json=TRIGGER_RESPONSE))
        mock_api.get(f"{BASE_PATH}/trig-1/runs").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "results": [{"id": "run-1", "status": "completed"}],
                        "pagination": {
                            "has_more": True,
                            "next_offset": "run-1",
                            "max_per_page": 1,
                        },
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "results": [{"id": "run-2", "status": "failed"}],
                        "pagination": {
                            "has_more": False,
                            "next_offset": None,
                            "max_per_page": 1,
                        },
                    },
                ),
            ]
        )
        trigger = repo.sandbox_trigger(
            name="validate",
            conditions=[],
            sandbox_config={"image": "python:3.10"},
        )
        runs = list(trigger.runs())
        assert len(runs) == 2
        assert runs[0].id == "run-1"
        assert runs[1].id == "run-2"
