"""Repository entity and Repositories collection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tilde._isoparse import parse_optional as _parse_dt
from tilde._output_stream import OutputStream
from tilde._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from tilde._value_types import RunResult

if TYPE_CHECKING:
    from datetime import datetime

    from tilde.client import Client
    from tilde.resources.commits import Commits
    from tilde.resources.connectors import RepositoryConnectors
    from tilde.resources.imports import Imports
    from tilde.resources.sandbox_triggers import SandboxTriggers
    from tilde.resources.sandboxes import Sandboxes
    from tilde.resources.secrets import Secrets
    from tilde.resources.sessions import Session
    from tilde.resources.shell import Shell


class Repository:
    """A Tilde repository."""

    def __init__(
        self,
        client: Client,
        org: str,
        name: str,
        *,
        id: str = "",
        organization_id: str = "",
        description: str = "",
        visibility: str = "",
        session_max_duration_days: int | None = None,
        retention_days: int | None = None,
        created_by_type: str = "",
        created_by: str = "",
        created_at: datetime | None = None,
    ) -> None:
        self._client = client
        self._org = org
        self.name = name
        self._id = id
        self._organization_id = organization_id
        self._description = description
        self._visibility = visibility
        self._session_max_duration_days = session_max_duration_days
        self._retention_days = retention_days
        self._created_by_type = created_by_type
        self._created_by = created_by
        self._created_at = created_at
        self._loaded = bool(id)

    def __repr__(self) -> str:
        return f"Repository({self._org}/{self.name})"

    @property
    def org(self) -> str:
        """Slug of the organization that owns this repository."""
        return self._org

    @property
    def _repo_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self.name}"

    def _populate(self, data: dict[str, Any]) -> None:
        self._id = data.get("id", self._id)
        self._organization_id = data.get("organization_id", self._organization_id)
        self._description = data.get("description", self._description)
        self._visibility = data.get("visibility", self._visibility)
        self._session_max_duration_days = data.get(
            "session_max_duration_days", self._session_max_duration_days
        )
        self._retention_days = data.get("retention_days", self._retention_days)
        self._created_by_type = data.get("created_by_type", self._created_by_type)
        self._created_by = data.get("created_by", self._created_by)
        created_at = _parse_dt(data.get("created_at"))
        if created_at is not None:
            self._created_at = created_at
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        data = self._client._get_json(self._repo_path)
        self._populate(data)

    def refresh(self) -> Repository:
        """Re-fetch this repository's metadata from the server."""
        self._loaded = False
        self._ensure_loaded()
        return self

    @classmethod
    def from_dict(cls, client: Client, org: str, d: dict[str, Any]) -> Repository:
        repo = cls(client, org, d.get("name", ""))
        repo._populate(d)
        return repo

    # -- Properties (lazy-loaded from the repo GET on first access) -----------

    @property
    def id(self) -> str:
        self._ensure_loaded()
        return self._id

    @property
    def organization_id(self) -> str:
        self._ensure_loaded()
        return self._organization_id

    @property
    def description(self) -> str:
        self._ensure_loaded()
        return self._description

    @property
    def visibility(self) -> str:
        self._ensure_loaded()
        return self._visibility

    @property
    def session_max_duration_days(self) -> int | None:
        self._ensure_loaded()
        return self._session_max_duration_days

    @property
    def retention_days(self) -> int | None:
        self._ensure_loaded()
        return self._retention_days

    @property
    def created_by_type(self) -> str:
        self._ensure_loaded()
        return self._created_by_type

    @property
    def created_by(self) -> str:
        self._ensure_loaded()
        return self._created_by

    @property
    def created_at(self) -> datetime | None:
        self._ensure_loaded()
        return self._created_at

    # -- Sessions -------------------------------------------------------------

    def session(self) -> Session:
        """Create a new editing session.

        Usable as a context manager for automatic rollback on error::

            with repo.session() as session:
                session.objects.put('data/report.csv', b'content')
                session.commit('update CSV files')
        """
        from tilde.resources.sessions import Session

        data = self._client._post_json(f"{self._repo_path}/sessions")
        return Session(self._client, self._org, self.name, data["session_id"])

    def attach(self, session_id: str) -> Session:
        """Attach to an existing session by ID."""
        from tilde.resources.sessions import Session

        return Session(self._client, self._org, self.name, session_id)

    # -- Sub-collections ------------------------------------------------------

    @property
    def commits(self) -> Commits:
        from tilde.resources.commits import Commits

        return Commits(self._client, self._org, self.name)

    @property
    def sandboxes(self) -> Sandboxes:
        from tilde.resources.sandboxes import Sandboxes

        return Sandboxes(self._client, self._org, self.name)

    @property
    def sandbox_triggers(self) -> SandboxTriggers:
        from tilde.resources.sandbox_triggers import SandboxTriggers

        return SandboxTriggers(self._client, self._org, self.name)

    @property
    def connectors(self) -> RepositoryConnectors:
        from tilde.resources.connectors import RepositoryConnectors

        return RepositoryConnectors(self._client, self._org, self.name)

    @property
    def imports(self) -> Imports:
        from tilde.resources.imports import Imports

        return Imports(self._client, self._org, self.name)

    @property
    def secrets(self) -> Secrets:
        from tilde.resources.secrets import Secrets

        return Secrets(self._client, f"{self._repo_path}/secrets")

    # -- Shell / execute ------------------------------------------------------

    def shell(
        self,
        *,
        image: str | None = None,
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        timeout: int | None = None,
        name: str | None = None,
        mountpoint: str | None = None,
        path_prefix: str | None = None,
    ) -> Shell:
        """Create an interactive sandbox shell.

        Returns a context manager that connects a WebSocket terminal::

            with repo.shell(image="python:3.12") as sh:
                result = sh.run("echo hello")
                print(result.stdout)
        """
        from tilde.resources.sandboxes import _create_sandbox
        from tilde.resources.shell import Shell

        _ = name  # reserved for future use
        resolved_image = image or self._client._config.default_sandbox_image
        sandbox = _create_sandbox(
            self._client,
            self._org,
            self.name,
            image=resolved_image,
            command=cmd,
            env=env,
            mountpoint=mountpoint,
            path_prefix=path_prefix,
            timeout_seconds=timeout,
            interactive=True,
        )
        return Shell(self._client, sandbox)

    def execute(
        self,
        command: str | list[str],
        *,
        image: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        check: bool = True,
        mountpoint: str | None = None,
        path_prefix: str | None = None,
    ) -> RunResult:
        """Run a single command in a sandbox and return the result."""
        import time

        from tilde.exceptions import CommandError, SandboxError
        from tilde.resources.sandboxes import _create_sandbox

        resolved_image = image or self._client._config.default_sandbox_image
        cmd_list = ["sh", "-c", command] if isinstance(command, str) else command

        sandbox = _create_sandbox(
            self._client,
            self._org,
            self.name,
            image=resolved_image,
            command=cmd_list,
            env=env,
            mountpoint=mountpoint,
            path_prefix=path_prefix,
            timeout_seconds=timeout,
        )

        poll_timeout = 300.0
        deadline = time.monotonic() + poll_timeout
        status = None
        while time.monotonic() < deadline:
            status = sandbox.status()
            if status.state in ("committed", "failed", "cancelled", "error", "awaiting_approval"):
                break
            time.sleep(1.0)
        else:
            raise SandboxError(f"Sandbox {sandbox.id} did not finish within {poll_timeout}s")

        stdout_bytes = b""
        try:
            with self._client._stream("GET", f"{sandbox._base_path}/logs/stdout") as resp:
                stdout_bytes = resp.read()
        except Exception:
            pass

        exit_code = status.exit_code if status is not None and status.exit_code is not None else -1
        result = RunResult(
            stdout=OutputStream(stdout_bytes),
            exit_code=exit_code,
        )

        if check and exit_code != 0:
            cmd_str = command if isinstance(command, str) else " ".join(command)
            raise CommandError(
                f"Command {cmd_str!r} exited with code {exit_code}",
                result=result,
                command=cmd_str,
            )

        return result

    # -- Mutations ------------------------------------------------------------

    def update(
        self,
        *,
        description: str | None = None,
        visibility: str | None = None,
        session_max_duration_days: int | None = None,
        retention_days: int | None = None,
    ) -> Repository:
        """Update repository settings."""
        body: dict[str, str | int] = {}
        if description is not None:
            body["description"] = description
        if visibility is not None:
            body["visibility"] = visibility
        if session_max_duration_days is not None:
            body["session_max_duration_days"] = session_max_duration_days
        if retention_days is not None:
            body["retention_days"] = retention_days
        data = self._client._put_json(self._repo_path, json=body)
        self._populate(data)
        return self

    def delete(self) -> None:
        """Delete this repository (soft delete)."""
        self._client._delete(self._repo_path)


class Repositories:
    """Repositories owned by an organization."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    def __repr__(self) -> str:
        return f"Repositories(org={self._org!r})"

    @property
    def _base_path(self) -> str:
        return f"/organizations/{self._org}/repositories"

    def list(
        self,
        *,
        after: str | None = None,
        amount: int | None = None,
        page_size: int | None = None,
    ) -> PaginatedIterator[Repository]:
        """List repositories in the organization."""
        initial_after = after
        client = self._client
        org = self._org

        def fetch_page(cursor: str | None) -> PageResult[Repository]:
            params: dict[str, str | int] = {
                "amount": page_size if page_size is not None else DEFAULT_PAGE_SIZE
            }
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            data = client._get_json(f"/organizations/{org}/repositories", params=params)
            items = [Repository.from_dict(client, org, d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page, limit=amount)

    def get(self, name: str) -> Repository:
        """Get a repository by name."""
        return Repository(self._client, self._org, name)

    def create(
        self,
        name: str,
        *,
        description: str = "",
        visibility: str = "private",
        session_max_duration_days: int | None = None,
        retention_days: int | None = None,
    ) -> Repository:
        """Create a repository."""
        body: dict[str, str | int] = {"name": name, "visibility": visibility}
        if description:
            body["description"] = description
        if session_max_duration_days is not None:
            body["session_max_duration_days"] = session_max_duration_days
        if retention_days is not None:
            body["retention_days"] = retention_days
        data = self._client._post_json(self._base_path, json=body)
        return Repository.from_dict(self._client, self._org, data)

    def delete(self, name: str) -> None:
        """Delete a repository by name."""
        self._client._delete(f"{self._base_path}/{name}")
