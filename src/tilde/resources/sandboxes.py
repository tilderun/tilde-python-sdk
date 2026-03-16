"""Sandbox resource for running containers against repository data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tilde._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator

if TYPE_CHECKING:
    from collections.abc import Iterator

if TYPE_CHECKING:
    import httpx

    from tilde.client import Client


class LogStream:
    """Streaming line iterator for sandbox stdout/stderr.

    Use as a context manager::

        with sandbox.status().stdout() as stream:
            for line in stream:
                print(line)
    """

    def __repr__(self) -> str:
        return f"LogStream(path='{self._path}')"

    def __init__(self, client: Client, path: str) -> None:
        self._client = client
        self._path = path
        self._cm: Any = None
        self._response: httpx.Response | None = None

    def __enter__(self) -> LogStream:
        self._cm = self._client._stream("GET", self._path)
        self._response = self._cm.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._cm is not None:
            self._cm.__exit__(*args)

    def __iter__(self) -> Iterator[str]:
        if self._response is None:
            raise RuntimeError("LogStream must be used as a context manager")
        return self._response.iter_lines()


class SandboxStatus:
    """Status snapshot of a sandbox with streaming log access.

    Returned by :meth:`SandboxResource.status`.
    """

    def __init__(
        self,
        client: Client,
        base_path: str,
        data: dict[str, Any],
    ) -> None:
        self._client = client
        self._base_path = base_path
        self.state: str = data.get("status", "")
        self.status_reason: str = data.get("status_reason", "")
        self.exit_code: int | None = data.get("exit_code")
        self.commit_id: str = data.get("commit_id", "")
        self.web_url: str = data.get("web_url", "")

    def __repr__(self) -> str:
        parts = [f"state='{self.state}'"]
        if self.exit_code is not None:
            parts.append(f"exit_code={self.exit_code}")
        if self.commit_id:
            parts.append(f"commit_id='{self.commit_id}'")
        if self.web_url:
            parts.append(f"web_url='{self.web_url}'")
        return f"SandboxStatus({', '.join(parts)})"

    def stdout(self) -> LogStream:
        """Stream sandbox stdout."""
        return LogStream(self._client, f"{self._base_path}/stdout")

    def stderr(self) -> LogStream:
        """Stream sandbox stderr."""
        return LogStream(self._client, f"{self._base_path}/stderr")


class SandboxResource:
    """A handle to a single sandbox.

    Returned by :meth:`Repository.sandbox` or when iterating
    :meth:`Repository.sandboxes`.
    """

    def __init__(self, client: Client, org: str, repo: str, sandbox_id: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo
        self._sandbox_id = sandbox_id

    def __repr__(self) -> str:
        return f"SandboxResource(id='{self._sandbox_id}')"

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}/sandboxes/{self._sandbox_id}"

    @property
    def id(self) -> str:
        return self._sandbox_id

    def status(self) -> SandboxStatus:
        """Get the current status of this sandbox."""
        data = self._client._get_json(f"{self._base_path}/status")
        return SandboxStatus(self._client, self._base_path, data)

    def cancel(self) -> None:
        """Cancel a running sandbox."""
        self._client._delete(self._base_path)

    @classmethod
    def _from_dict(
        cls,
        client: Client,
        org: str,
        repo: str,
        d: dict[str, Any],
    ) -> SandboxResource:
        return cls(client, org, repo, d.get("id", ""))


def create_sandbox(
    client: Client,
    org: str,
    repo: str,
    *,
    image: str,
    command: list[str] | None = None,
    env: dict[str, str] | None = None,
    mountpoint: str | None = None,
    path_prefix: str | None = None,
    timeout_seconds: int | None = None,
    run_as: dict[str, str] | None = None,
    interactive: bool = False,
) -> SandboxResource:
    """Create and run a sandbox (called by Repository.sandbox)."""
    body: dict[str, Any] = {"image": image}
    if interactive:
        body["interactive"] = True
    if command is not None:
        body["command"] = command
    if env is not None:
        body["env_vars"] = env
    if mountpoint is not None:
        body["mountpoint"] = mountpoint
    if path_prefix is not None:
        body["path_prefix"] = path_prefix
    if timeout_seconds is not None:
        body["timeout_seconds"] = timeout_seconds
    if run_as is not None:
        body["run_as"] = run_as
    base = f"/organizations/{org}/repositories/{repo}/sandboxes"
    data = client._post_json(base, json=body)
    sandbox_id = data["sandbox_id"]
    return SandboxResource(client, org, repo, sandbox_id)


def list_sandboxes(
    client: Client,
    org: str,
    repo: str,
    *,
    after: str | None = None,
) -> PaginatedIterator[SandboxResource]:
    """List sandboxes in a repository (called by Repository.sandboxes)."""
    initial_after = after
    base = f"/organizations/{org}/repositories/{repo}/sandboxes"

    def fetch_page(cursor: str | None) -> PageResult[SandboxResource]:
        params: dict[str, str | int] = {"amount": DEFAULT_PAGE_SIZE}
        effective_after = cursor if cursor is not None else initial_after
        if effective_after is not None:
            params["after"] = effective_after
        data = client._get_json(base, params=params)
        items = [SandboxResource._from_dict(client, org, repo, d) for d in data.get("results", [])]
        pagination = data.get("pagination", {})
        return PageResult(
            items=items,
            has_more=pagination.get("has_more", False),
            next_offset=pagination.get("next_offset"),
            max_per_page=pagination.get("max_per_page"),
        )

    return PaginatedIterator(fetch_page)
