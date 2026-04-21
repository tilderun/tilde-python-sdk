"""Sandbox entity and Sandboxes collection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tilde._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator

if TYPE_CHECKING:
    import builtins
    from collections.abc import Iterator

    import httpx

    from tilde.client import Client


class LogStream:
    """Streaming line iterator for sandbox output logs.

    Use as a context manager::

        with sandbox.status().stdout() as stream:
            for line in stream:
                print(line)
    """

    def __init__(self, client: Client, path: str) -> None:
        self._client = client
        self._path = path
        self._cm: Any = None
        self._response: httpx.Response | None = None

    def __repr__(self) -> str:
        return f"LogStream(path={self._path!r})"

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
    """Status snapshot of a sandbox with streaming log access."""

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
        self.error_message: str = data.get("error_message", "")

    def __repr__(self) -> str:
        parts = [f"state={self.state!r}"]
        if self.exit_code is not None:
            parts.append(f"exit_code={self.exit_code}")
        if self.commit_id:
            parts.append(f"commit_id={self.commit_id!r}")
        if self.web_url:
            parts.append(f"web_url={self.web_url!r}")
        if self.error_message:
            parts.append(f"error_message={self.error_message!r}")
        return f"SandboxStatus({', '.join(parts)})"

    def stdout(self) -> LogStream:
        """Stream merged sandbox stdout and stderr."""
        return LogStream(self._client, f"{self._base_path}/logs/stdout")

    def network(self) -> LogStream:
        """Stream sandbox outbound network logs (NDJSON)."""
        return LogStream(self._client, f"{self._base_path}/logs/network")


class Sandbox:
    """A handle to a single sandbox run."""

    def __init__(self, client: Client, org: str, repo: str, id: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo
        self.id = id

    def __repr__(self) -> str:
        return f"Sandbox(id={self.id!r})"

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}/sandboxes/{self.id}"

    @classmethod
    def from_dict(cls, client: Client, org: str, repo: str, d: dict[str, Any]) -> Sandbox:
        return cls(client, org, repo, d.get("id", ""))

    def status(self) -> SandboxStatus:
        data = self._client._get_json(f"{self._base_path}/status")
        return SandboxStatus(self._client, self._base_path, data)

    def cancel(self) -> None:
        """Roll back the sandbox; any session-level changes are discarded."""
        self._client._delete(self._base_path)

    def delete(self) -> None:
        """Alias for :meth:`cancel`."""
        self.cancel()

    def finish(self) -> None:
        """Gracefully finish a service-mode sandbox (commit path).

        Returns immediately after the shutdown is dispatched; callers poll
        :meth:`status` to observe the final ``committed`` state.
        """
        self._client._post(f"{self._base_path}/finish")


class Sandboxes:
    """Sandboxes in a repository."""

    def __init__(self, client: Client, org: str, repo: str) -> None:
        self._client = client
        self._org = org
        self._repo = repo

    def __repr__(self) -> str:
        return f"Sandboxes({self._org}/{self._repo})"

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._repo}/sandboxes"

    def list(
        self,
        *,
        after: str | None = None,
        amount: int | None = None,
        page_size: int | None = None,
    ) -> PaginatedIterator[Sandbox]:
        initial_after = after
        client = self._client
        org = self._org
        repo = self._repo
        base = self._base_path

        def fetch_page(cursor: str | None) -> PageResult[Sandbox]:
            params: dict[str, str | int] = {
                "amount": page_size if page_size is not None else DEFAULT_PAGE_SIZE
            }
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            data = client._get_json(base, params=params)
            items = [Sandbox.from_dict(client, org, repo, d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page, limit=amount)

    def get(self, sandbox_id: str) -> Sandbox:
        return Sandbox(self._client, self._org, self._repo, sandbox_id)

    def create(
        self,
        *,
        image: str,
        command: builtins.list[str] | None = None,
        env: dict[str, str] | None = None,
        mountpoint: str | None = None,
        path_prefix: str | None = None,
        timeout_seconds: int | None = None,
        run_as: dict[str, str] | None = None,
    ) -> Sandbox:
        """Create and run a sandbox."""
        return _create_sandbox(
            self._client,
            self._org,
            self._repo,
            image=image,
            command=command,
            env=env,
            mountpoint=mountpoint,
            path_prefix=path_prefix,
            timeout_seconds=timeout_seconds,
            run_as=run_as,
        )


def _create_sandbox(
    client: Client,
    org: str,
    repo: str,
    *,
    image: str,
    command: builtins.list[str] | None = None,
    env: dict[str, str] | None = None,
    mountpoint: str | None = None,
    path_prefix: str | None = None,
    timeout_seconds: int | None = None,
    run_as: dict[str, str] | None = None,
    mode: str | None = None,
) -> Sandbox:
    """Internal helper shared by ``Sandboxes.create`` and ``Repository.execute``.

    ``mode`` is one of ``"one-shot"``, ``"interactive"``, or ``"service"``
    (see the ``CreateSandboxRequest`` schema).  ``None`` falls back to the
    server default (``"one-shot"``).
    """
    body: dict[str, Any] = {"image": image}
    if mode is not None:
        body["mode"] = mode
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
    return Sandbox(client, org, repo, data["sandbox_id"])
