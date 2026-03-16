"""Interactive shell for running commands in a sandbox via WebSocket."""

from __future__ import annotations

import contextlib
import time
import uuid
import warnings
from typing import TYPE_CHECKING

from websockets.sync.client import connect as ws_connect

from tilde._output_stream import OutputStream
from tilde.exceptions import CommandError, SandboxError
from tilde.models import RunResult

if TYPE_CHECKING:
    from types import TracebackType

    from websockets.sync.client import ClientConnection

    from tilde.client import Client
    from tilde.resources.sandboxes import SandboxResource

_POLL_INTERVAL = 1.0
_POLL_TIMEOUT = 300.0


class Shell:
    """Interactive sandbox shell with WebSocket terminal communication.

    Use as a context manager::

        with repo.shell(image="python:3.12") as sh:
            result = sh.run("echo hello")
            print(result.stdout)

    On clean exit the sandbox is committed. On exception it is cancelled.
    """

    def __init__(
        self,
        client: Client,
        sandbox: SandboxResource,
    ) -> None:
        self._client = client
        self._sandbox = sandbox
        self._ws: ClientConnection | None = None

    def __repr__(self) -> str:
        return f"Shell(sandbox='{self._sandbox.id}')"

    def __enter__(self) -> Shell:
        self._wait_for_running()
        self._connect_ws()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self._close_ws()
            self._sandbox.cancel()
            return

        # Clean exit — send exit command, close WebSocket, wait for sandbox to finish
        if self._ws is not None:
            with contextlib.suppress(Exception):
                self._ws.send("exit\n")
        self._close_ws()
        self._wait_for_terminal_state()

    def run(self, cmd: str, *, check: bool = False) -> RunResult:
        """Execute a command in the sandbox and return the result.

        Args:
            cmd: Shell command to execute.
            check: If ``True``, raise :class:`~tilde.exceptions.CommandError`
                on non-zero exit code.

        Returns:
            A :class:`~tilde.models.RunResult` with stdout, stderr, and exit_code.
        """
        if self._ws is None:
            raise SandboxError("Shell is not connected")

        marker = uuid.uuid4().hex
        begin_marker = f"__TILDE_BEGIN_{marker}__"
        end_marker = f"__TILDE_END_{marker}__"

        # Send the command with markers to delimit output
        wrapped = f"{cmd}; __ec=$?; echo '\\n{begin_marker}'; echo $__ec; echo '{end_marker}'\n"
        self._ws.send(wrapped)

        # Read frames until we find the end marker
        buf = ""
        while end_marker not in buf:
            try:
                frame = self._ws.recv(timeout=30)
            except TimeoutError as exc:
                raise SandboxError(f"Timeout waiting for command output: {cmd}") from exc
            if isinstance(frame, bytes):
                buf += frame.decode("utf-8", errors="replace")
            else:
                buf += frame

        # Parse output: everything before begin_marker is stdout,
        # between begin_marker and end_marker is exit code
        before_begin, _, after_begin = buf.partition(begin_marker)
        between, _, _ = after_begin.partition(end_marker)

        # The exit code is on the line after begin_marker
        exit_code_str = between.strip()
        try:
            exit_code = int(exit_code_str)
        except ValueError:
            exit_code = -1

        # stdout is everything before the begin marker, minus the echoed command
        stdout = _clean_output(before_begin, cmd)

        result = RunResult(stdout=OutputStream(stdout.encode("utf-8")), exit_code=exit_code)

        if check and exit_code != 0:
            raise CommandError(
                f"Command {cmd!r} exited with code {exit_code}",
                result=result,
                command=cmd,
            )

        return result

    # -- Internal helpers ----------------------------------------------------

    def _wait_for_running(self) -> None:
        """Poll sandbox status until it reaches 'running' state."""
        deadline = time.monotonic() + _POLL_TIMEOUT
        while time.monotonic() < deadline:
            status = self._sandbox.status()
            if status.state == "running":
                return
            if status.state in ("failed", "cancelled", "committed", "error"):
                raise SandboxError(
                    f"Sandbox {self._sandbox.id} entered terminal state "
                    f"'{status.state}' before becoming ready"
                )
            time.sleep(_POLL_INTERVAL)
        raise SandboxError(
            f"Sandbox {self._sandbox.id} did not reach 'running' state within {_POLL_TIMEOUT}s"
        )

    def _connect_ws(self) -> None:
        """Open a WebSocket connection to the sandbox terminal."""
        api_key = self._client._ensure_api_key()
        ws_url = (
            f"{self._client._ws_base_url}"
            f"/organizations/{self._sandbox._org}"
            f"/repositories/{self._sandbox._repo}"
            f"/sandboxes/{self._sandbox._sandbox_id}/terminal"
        )
        self._ws = ws_connect(
            ws_url,
            additional_headers={"Authorization": f"Bearer {api_key}"},
        )

    def _close_ws(self) -> None:
        """Close the WebSocket connection if open."""
        if self._ws is not None:
            with contextlib.suppress(Exception):
                self._ws.close()
            self._ws = None

    def _wait_for_terminal_state(self) -> None:
        """Poll sandbox status until it reaches a terminal state after exit."""
        deadline = time.monotonic() + _POLL_TIMEOUT
        while time.monotonic() < deadline:
            status = self._sandbox.status()
            if status.state == "committed":
                return
            if status.state == "awaiting_approval":
                warnings.warn(
                    f"Sandbox {self._sandbox.id} requires approval: {status.web_url}",
                    UserWarning,
                    stacklevel=3,
                )
                return
            if status.state in ("failed", "cancelled", "error"):
                raise SandboxError(f"Sandbox {self._sandbox.id} ended with state '{status.state}'")
            time.sleep(_POLL_INTERVAL)
        raise SandboxError(
            f"Sandbox {self._sandbox.id} did not reach terminal state within {_POLL_TIMEOUT}s"
        )


def _clean_output(raw: str, cmd: str) -> str:
    """Strip echoed command and trailing whitespace from shell output."""
    # The terminal often echoes the command back; remove it
    lines = raw.split("\n")
    # Remove leading empty lines and command echo
    cleaned: list[str] = []
    found_content = False
    for line in lines:
        stripped = line.strip()
        if not found_content:
            # Skip empty lines and lines that look like the echoed command
            if not stripped:
                continue
            if cmd in stripped:
                continue
            found_content = True
        cleaned.append(line)
    # Remove trailing empty lines
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()
    return "\n".join(cleaned)
