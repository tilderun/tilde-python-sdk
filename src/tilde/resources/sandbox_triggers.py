"""Sandbox trigger resource for automated sandbox execution on commits."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tilde._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from tilde.models import SandboxTriggerData, SandboxTriggerRunData

if TYPE_CHECKING:
    from tilde.client import Client


class SandboxTriggerResource:
    """A handle to a single sandbox trigger.

    Returned by :meth:`Repository.sandbox_trigger` or when iterating
    :meth:`Repository.sandbox_triggers`.
    """

    def __init__(self, client: Client, org: str, repo: str, trigger_id: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo
        self._trigger_id = trigger_id

    def __repr__(self) -> str:
        return f"SandboxTriggerResource(id='{self._trigger_id}')"

    @property
    def _base_path(self) -> str:
        return (
            f"/organizations/{self._org}/repositories/{self._repo}"
            f"/sandbox-triggers/{self._trigger_id}"
        )

    @property
    def id(self) -> str:
        return self._trigger_id

    def get(self) -> SandboxTriggerData:
        """Get the full trigger data."""
        data = self._client._get_json(self._base_path)
        return SandboxTriggerData.from_dict(data)

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        conditions: list[dict[str, Any]] | None = None,
        sandbox_config: dict[str, Any] | None = None,
        run_as: dict[str, str] | None = None,
    ) -> SandboxTriggerData:
        """Update (full replacement) of this trigger."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if conditions is not None:
            body["conditions"] = conditions
        if sandbox_config is not None:
            body["sandbox_config"] = sandbox_config
        if run_as is not None:
            body["run_as"] = run_as
        data = self._client._put_json(self._base_path, json=body)
        return SandboxTriggerData.from_dict(data)

    def toggle(self, *, enabled: bool) -> SandboxTriggerData:
        """Enable or disable this trigger."""
        data = self._client._patch_json(self._base_path, json={"enabled": enabled})
        return SandboxTriggerData.from_dict(data)

    def delete(self) -> None:
        """Delete this trigger."""
        self._client._delete(self._base_path)

    def runs(self, *, after: str | None = None) -> PaginatedIterator[SandboxTriggerRunData]:
        """List runs for this trigger."""
        initial_after = after
        runs_path = f"{self._base_path}/runs"

        def fetch_page(cursor: str | None) -> PageResult[SandboxTriggerRunData]:
            params: dict[str, str | int] = {"amount": DEFAULT_PAGE_SIZE}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            data = self._client._get_json(runs_path, params=params)
            items = [SandboxTriggerRunData.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    @classmethod
    def _from_dict(
        cls,
        client: Client,
        org: str,
        repo: str,
        d: dict[str, Any],
    ) -> SandboxTriggerResource:
        return cls(client, org, repo, d.get("id", ""))


def create_sandbox_trigger(
    client: Client,
    org: str,
    repo: str,
    *,
    name: str,
    conditions: list[dict[str, Any]],
    sandbox_config: dict[str, Any],
    description: str = "",
    run_as: dict[str, str] | None = None,
) -> SandboxTriggerResource:
    """Create a sandbox trigger (called by Repository.sandbox_trigger)."""
    body: dict[str, Any] = {
        "name": name,
        "conditions": conditions,
        "sandbox_config": sandbox_config,
    }
    if description:
        body["description"] = description
    if run_as is not None:
        body["run_as"] = run_as
    base = f"/organizations/{org}/repositories/{repo}/sandbox-triggers"
    data = client._post_json(base, json=body)
    trigger_id = data.get("id", "")
    return SandboxTriggerResource(client, org, repo, trigger_id)


def list_sandbox_triggers(
    client: Client,
    org: str,
    repo: str,
    *,
    after: str | None = None,
) -> PaginatedIterator[SandboxTriggerResource]:
    """List sandbox triggers in a repository (called by Repository.sandbox_triggers)."""
    initial_after = after
    base = f"/organizations/{org}/repositories/{repo}/sandbox-triggers"

    def fetch_page(cursor: str | None) -> PageResult[SandboxTriggerResource]:
        params: dict[str, str | int] = {"amount": DEFAULT_PAGE_SIZE}
        effective_after = cursor if cursor is not None else initial_after
        if effective_after is not None:
            params["after"] = effective_after
        data = client._get_json(base, params=params)
        items = [
            SandboxTriggerResource._from_dict(client, org, repo, d) for d in data.get("results", [])
        ]
        pagination = data.get("pagination", {})
        return PageResult(
            items=items,
            has_more=pagination.get("has_more", False),
            next_offset=pagination.get("next_offset"),
            max_per_page=pagination.get("max_per_page"),
        )

    return PaginatedIterator(fetch_page)
