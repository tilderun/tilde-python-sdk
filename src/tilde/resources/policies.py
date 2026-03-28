"""Policy resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tilde._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from tilde.models import (
    AttachmentRecord,
    EffectivePolicy,
    Policy,
    PolicyDetail,
    PolicySummary,
    ValidationResult,
)

if TYPE_CHECKING:
    import builtins

    from tilde.client import Client


class PolicyCollection:
    """CRUD operations for policies in an organization."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/policies"

    def create(self, name: str, policy_text: str, description: str = "") -> Policy:
        """Create a policy."""
        body: dict[str, str] = {"name": name, "policy_text": policy_text}
        if description:
            body["description"] = description
        data = self._client._post_json(self._base_path, json=body)
        return Policy.from_dict(data)

    def list(self, *, after: str | None = None) -> PaginatedIterator[PolicySummary]:
        """List policies (paginated)."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[PolicySummary]:
            params: dict[str, str | int] = {}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            params["amount"] = DEFAULT_PAGE_SIZE
            data = self._client._get_json(self._base_path, params=params)
            items = [PolicySummary.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    def get(self, policy_id: str) -> PolicyDetail:
        """Get a policy with attachments."""
        data = self._client._get_json(f"{self._base_path}/{policy_id}")
        return PolicyDetail.from_dict(data)

    def update(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        policy_text: str | None = None,
    ) -> Policy:
        """Update a policy."""
        body: dict[str, str] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if policy_text is not None:
            body["policy_text"] = policy_text
        data = self._client._put_json(f"{self._base_path}/{policy_id}", json=body)
        return Policy.from_dict(data)

    def delete(self, policy_id: str) -> None:
        """Delete a policy."""
        self._client._delete(f"{self._base_path}/{policy_id}")

    def validate(self, policy_text: str) -> ValidationResult:
        """Validate a policy document without saving."""
        data = self._client._post_json(
            f"{self._base_path}:validate",
            json={"policy_text": policy_text},
        )
        return ValidationResult.from_dict(data)

    def generate(self, prompt: str) -> str:
        """Generate a policy from a natural language prompt.

        Returns the generated policy source code.
        """
        data = self._client._post_json(
            f"{self._base_path}:generate",
            json={"prompt": prompt},
        )
        return str(data["policy_text"])

    def attach(self, policy_id: str, principal_type: str, principal_id: str) -> None:
        """Attach a policy to a user or group."""
        self._client._post(
            f"{self._base_path}/{policy_id}/attachments",
            json={"principal_type": principal_type, "principal_id": principal_id},
        )

    def detach(self, policy_id: str, principal_type: str, principal_id: str) -> None:
        """Detach a policy from a user or group."""
        self._client._delete(
            f"{self._base_path}/{policy_id}/attachments",
            params={"principal_type": principal_type, "principal_id": principal_id},
        )

    def list_attachments(self) -> builtins.list[AttachmentRecord]:
        """List all policy attachments in the organization."""
        data = self._client._get_json(f"/organizations/{self._org}/attachments")
        return [AttachmentRecord.from_dict(d) for d in data.get("results", [])]

    def effective_policies(
        self,
        user_id: str | None = None,
        *,
        principal_type: str | None = None,
        principal_id: str | None = None,
    ) -> builtins.list[EffectivePolicy]:
        """Get effective policies for a principal.

        Args:
            user_id: User ID (backward-compatible; prefer principal_type + principal_id).
            principal_type: Principal type (e.g. ``"user"``, ``"agent"``).
            principal_id: Principal ID.
        """
        params: dict[str, str] = {}
        if user_id is not None:
            params["user_id"] = user_id
        if principal_type is not None:
            params["principal_type"] = principal_type
        if principal_id is not None:
            params["principal_id"] = principal_id
        data = self._client._get_json(
            f"/organizations/{self._org}/effective-policies",
            params=params,
        )
        return [EffectivePolicy.from_dict(d) for d in data.get("results", [])]
