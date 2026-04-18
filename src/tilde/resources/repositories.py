"""Repository resource with lazy-loaded properties."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tilde._output_stream import OutputStream
from tilde._pagination import DEFAULT_PAGE_SIZE, PageResult, PaginatedIterator
from tilde.models import CommitData, RepositoryData, RunResult, SecretEntry, _parse_dt

if TYPE_CHECKING:
    from datetime import datetime

    from tilde.client import Client
    from tilde.resources.connectors import RepoConnectorCollection
    from tilde.resources.imports import ImportResource
    from tilde.resources.sandbox_triggers import SandboxTriggerResource
    from tilde.resources.sandboxes import SandboxResource
    from tilde.resources.secrets import SecretManager
    from tilde.resources.sessions import Session
    from tilde.resources.shell import Shell


class OrgRepositoryCollection:
    """Repository operations within an organization."""

    def __init__(self, client: Client, org: str) -> None:
        self._client = client
        self._org = org

    def create(
        self,
        name: str,
        *,
        description: str = "",
        visibility: str = "private",
        session_max_duration_days: int | None = None,
        retention_days: int | None = None,
    ) -> RepositoryData:
        """Create a repository.

        Args:
            name: Repository name.
            description: Optional description.
            visibility: ``"private"`` (default) or ``"public"``.
            session_max_duration_days: Maximum days a session can remain open.
            retention_days: Days of commit history to retain.
        """
        body: dict[str, str | int] = {"name": name, "visibility": visibility}
        if description:
            body["description"] = description
        if session_max_duration_days is not None:
            body["session_max_duration_days"] = session_max_duration_days
        if retention_days is not None:
            body["retention_days"] = retention_days
        data = self._client._post_json(f"/organizations/{self._org}/repositories", json=body)
        return RepositoryData.from_dict(data)

    def list(self, *, after: str | None = None) -> PaginatedIterator[RepositoryData]:
        """List repositories in the organization."""
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[RepositoryData]:
            params: dict[str, str | int] = {"amount": DEFAULT_PAGE_SIZE}
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            data = self._client._get_json(f"/organizations/{self._org}/repositories", params=params)
            items = [RepositoryData.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)


class Repository:
    """A Tilde repository.  Properties are lazy-loaded on first access."""

    def __init__(self, client: Client, org: str, name: str) -> None:
        self._client = client
        self._org = org
        self._name = name
        self._loaded = False
        self._raw: dict[str, Any] = {}

    def __repr__(self) -> str:
        return f"Repository('{self._org}/{self._name}')"

    @property
    def _repo_path(self) -> str:
        return f"/organizations/{self._org}/repositories/{self._name}"

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._raw = self._client._get_json(self._repo_path)
        self._loaded = True

    # -- Lazy-loaded properties -----------------------------------------------

    @property
    def id(self) -> str:
        self._ensure_loaded()
        return str(self._raw.get("id", ""))

    @property
    def description(self) -> str:
        self._ensure_loaded()
        return str(self._raw.get("description", ""))

    @property
    def visibility(self) -> str:
        self._ensure_loaded()
        return str(self._raw.get("visibility", ""))

    @property
    def session_max_duration_days(self) -> int | None:
        self._ensure_loaded()
        return self._raw.get("session_max_duration_days")

    @property
    def retention_days(self) -> int | None:
        self._ensure_loaded()
        return self._raw.get("retention_days")

    @property
    def created_by(self) -> str:
        self._ensure_loaded()
        return str(self._raw.get("created_by", ""))

    @property
    def created_at(self) -> datetime | None:
        self._ensure_loaded()
        return _parse_dt(self._raw.get("created_at"))

    # -- Sessions -------------------------------------------------------------

    def session(self) -> Session:
        """Create a new editing session.

        Can be used as a context manager for automatic rollback on error::

            with repo.session() as session:
                session.objects.put('data/report.csv', b'content')
                session.commit('update CSV files')

        Or used explicitly::

            session = repo.session()
            session.objects.put('data/file.csv', b'content')
            session.commit('my changes')

        Returns:
            A :class:`~tilde.resources.sessions.Session`.
        """
        from tilde.resources.sessions import Session

        data = self._client._post_json(f"{self._repo_path}/sessions")
        session_id = data["session_id"]
        return Session(self._client, self._org, self._name, session_id)

    def attach(self, session_id: str) -> Session:
        """Attach to an existing session by ID.

        Useful for resuming a session from another thread, process, or machine::

            session = repo.attach(session_id)
            session.objects.put('data/file.csv', b'content')
            session.commit('my changes')

        Args:
            session_id: The session ID to attach to.

        Returns:
            A :class:`~tilde.resources.sessions.Session`.
        """
        from tilde.resources.sessions import Session

        return Session(self._client, self._org, self._name, session_id)

    # -- Timeline (commit log) ------------------------------------------------

    def timeline(
        self,
        *,
        ref: str | None = None,
        after: str | None = None,
        amount: int | None = None,
    ) -> PaginatedIterator[CommitData]:
        """List commits in the repository (newest first).

        Args:
            ref: Branch name, tag name, or commit ID. Defaults to the
                repository's default branch.
            after: Pagination cursor.
            amount: Page size (default 100).

        Returns:
            An auto-paginating iterator of :class:`~tilde.models.CommitData`.
        """
        initial_after = after

        def fetch_page(cursor: str | None) -> PageResult[CommitData]:
            params: dict[str, str | int] = {}
            if ref is not None:
                params["ref"] = ref
            effective_after = cursor if cursor is not None else initial_after
            if effective_after is not None:
                params["after"] = effective_after
            if amount is not None:
                params["amount"] = amount
            else:
                params["amount"] = DEFAULT_PAGE_SIZE
            data = self._client._get_json(f"{self._repo_path}/log", params=params)
            items = [CommitData.from_dict(d) for d in data.get("results", [])]
            pagination = data.get("pagination", {})
            return PageResult(
                items=items,
                has_more=pagination.get("has_more", False),
                next_offset=pagination.get("next_offset"),
                max_per_page=pagination.get("max_per_page"),
            )

        return PaginatedIterator(fetch_page)

    # -- Sandboxes -------------------------------------------------------------

    def sandbox(
        self,
        *,
        image: str,
        command: list[str] | None = None,
        env: dict[str, str] | None = None,
        mountpoint: str | None = None,
        path_prefix: str | None = None,
        timeout_seconds: int | None = None,
        run_as: dict[str, str] | None = None,
    ) -> SandboxResource:
        """Create and run a sandbox.

        Args:
            image: Image ID from the server-configured allowlist
                (e.g. ``"python-312"``, ``"ubuntu"``).
            command: Command to execute in the container.
            env: Environment variables for the container.
            mountpoint: Path inside the container where data is mounted
                (default ``"/sandbox"``).
            path_prefix: Path prefix within the repository to mount
                (default ``""``).
            timeout_seconds: Maximum execution time in seconds.
            run_as: Run as a different principal (``{"type": "agent", "id": "..."}``)
        """
        from tilde.resources.sandboxes import create_sandbox

        return create_sandbox(
            self._client,
            self._org,
            self._name,
            image=image,
            command=command,
            env=env,
            mountpoint=mountpoint,
            path_prefix=path_prefix,
            timeout_seconds=timeout_seconds,
            run_as=run_as,
        )

    def sandboxes(self, *, after: str | None = None) -> PaginatedIterator[SandboxResource]:
        """List sandboxes in this repository."""
        from tilde.resources.sandboxes import list_sandboxes

        return list_sandboxes(self._client, self._org, self._name, after=after)

    # -- Interactive shell & execute ------------------------------------------

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

            with repo.shell(image="python-312") as sh:
                result = sh.run("echo hello")
                print(result.stdout)

        Args:
            image: Image ID from the server-configured allowlist
                (default: configured ``default_sandbox_image``).
            env: Environment variables for the container.
            cmd: Entrypoint command override.
            timeout: Maximum execution time in seconds.
            name: Optional sandbox name.
            mountpoint: Mount path inside the container.
            path_prefix: Repository path prefix to mount.
        """
        from tilde.resources.sandboxes import create_sandbox
        from tilde.resources.shell import Shell

        resolved_image = image or self._client._config.default_sandbox_image
        sandbox = create_sandbox(
            self._client,
            self._org,
            self._name,
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
        """Run a single command in a sandbox and return the result.

        This is a convenience wrapper that creates a non-interactive sandbox,
        waits for it to finish, and reads its output::

            result = repo.execute("python train.py")
            print(result.stdout)

        Args:
            command: Shell command string or list of args.
            image: Image ID from the server-configured allowlist
                (default: configured ``default_sandbox_image``).
            env: Environment variables for the container.
            timeout: Maximum execution time in seconds.
            check: If ``True`` (default), raise
                :class:`~tilde.exceptions.CommandError` on non-zero exit.
            mountpoint: Mount path inside the container.
            path_prefix: Repository path prefix to mount.
        """
        import time

        from tilde.exceptions import CommandError, SandboxError
        from tilde.models import RunResult
        from tilde.resources.sandboxes import create_sandbox

        resolved_image = image or self._client._config.default_sandbox_image
        cmd_list = ["sh", "-c", command] if isinstance(command, str) else command

        sandbox = create_sandbox(
            self._client,
            self._org,
            self._name,
            image=resolved_image,
            command=cmd_list,
            env=env,
            mountpoint=mountpoint,
            path_prefix=path_prefix,
            timeout_seconds=timeout,
        )

        # Poll until terminal state
        poll_timeout = 300.0
        deadline = time.monotonic() + poll_timeout
        while time.monotonic() < deadline:
            status = sandbox.status()
            if status.state in ("committed", "failed", "cancelled", "error", "awaiting_approval"):
                break
            time.sleep(1.0)
        else:
            raise SandboxError(f"Sandbox {sandbox.id} did not finish within {poll_timeout}s")

        # Read stdout and stderr
        stdout_bytes = b""
        stderr_bytes = b""
        try:
            with self._client._stream("GET", f"{sandbox._base_path}/stdout") as resp:
                stdout_bytes = resp.read()
        except Exception:
            pass
        try:
            with self._client._stream("GET", f"{sandbox._base_path}/stderr") as resp:
                stderr_bytes = resp.read()
        except Exception:
            pass

        exit_code = status.exit_code if status.exit_code is not None else -1
        result = RunResult(
            stdout=OutputStream(stdout_bytes),
            exit_code=exit_code,
            stderr=OutputStream(stderr_bytes),
        )

        if check and exit_code != 0:
            cmd_str = command if isinstance(command, str) else " ".join(command)
            raise CommandError(
                f"Command {cmd_str!r} exited with code {exit_code}",
                result=result,
                command=cmd_str,
            )

        return result

    # -- Sandbox Triggers ------------------------------------------------------

    def sandbox_trigger(
        self,
        *,
        name: str,
        conditions: list[dict[str, Any]],
        sandbox_config: dict[str, Any],
        description: str = "",
        run_as: dict[str, str] | None = None,
    ) -> SandboxTriggerResource:
        """Create a sandbox trigger.

        Args:
            name: Trigger name.
            conditions: List of condition dicts (``type``, ``prefix``/``path``, ``diff_type``).
            sandbox_config: Sandbox configuration dict (``image``, ``command``, etc.).
            description: Optional description.
            run_as: Run as a different principal (``{"type": "agent", "id": "..."}``)
        """
        from tilde.resources.sandbox_triggers import create_sandbox_trigger

        return create_sandbox_trigger(
            self._client,
            self._org,
            self._name,
            name=name,
            conditions=conditions,
            sandbox_config=sandbox_config,
            description=description,
            run_as=run_as,
        )

    def sandbox_triggers(
        self, *, after: str | None = None
    ) -> PaginatedIterator[SandboxTriggerResource]:
        """List sandbox triggers in this repository."""
        from tilde.resources.sandbox_triggers import list_sandbox_triggers

        return list_sandbox_triggers(self._client, self._org, self._name, after=after)

    # -- Secrets ---------------------------------------------------------------

    @property
    def secret(self) -> SecretManager:
        """Access secret operations for this repository."""
        from tilde.resources.secrets import SecretManager

        return SecretManager(self._client, f"{self._repo_path}/secrets")

    def secrets(self) -> list[SecretEntry]:
        """List secrets in this repository (keys and metadata only)."""
        return self.secret.list()

    # -- Sub-resources --------------------------------------------------------

    @property
    def connectors(self) -> RepoConnectorCollection:
        from tilde.resources.connectors import RepoConnectorCollection

        return RepoConnectorCollection(self._client, self._org, self._name)

    @property
    def imports(self) -> ImportResource:
        from tilde.resources.imports import ImportResource

        return ImportResource(self._client, self._org, self._name)

    # -- Mutations ------------------------------------------------------------

    def update(
        self,
        *,
        description: str | None = None,
        visibility: str | None = None,
        session_max_duration_days: int | None = None,
        retention_days: int | None = None,
    ) -> RepositoryData:
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
        self._raw = data
        self._loaded = True
        return RepositoryData.from_dict(data)

    def delete(self) -> None:
        """Delete this repository (soft delete)."""
        self._client._delete(self._repo_path)
