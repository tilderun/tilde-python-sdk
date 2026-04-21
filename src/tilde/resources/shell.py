"""Shell: run commands in a sandbox over the dedicated /exec WebSocket."""

from __future__ import annotations

import contextlib
import json
import time
from typing import TYPE_CHECKING, Any

from websockets.sync.client import connect as ws_connect

from tilde._output_stream import OutputStream
from tilde._value_types import RunResult
from tilde.exceptions import CommandError, SandboxError

if TYPE_CHECKING:
    from types import TracebackType

    from websockets.sync.client import ClientConnection

    from tilde.client import Client
    from tilde.resources.sandboxes import Sandbox

_POLL_INTERVAL = 1.0
_POLL_TIMEOUT = 300.0
_CMD_TIMEOUT = 300.0

# Frame protocol for the per-call ``/exec`` WebSocket — first byte is the type.
_FRAME_LAUNCH = 0x00  # client → server: JSON {"cmd":[...], "env":{...}, "cwd":"..."}
_FRAME_STDIN = 0x01  # client → server: raw stdin bytes
_FRAME_STDIN_CLOSE = 0x02  # client → server: close child stdin (EOF)
_FRAME_STDOUT = 0x03  # server → client: raw stdout bytes
_FRAME_STDERR = 0x04  # server → client: raw stderr bytes
_FRAME_EXIT = 0x05  # server → client: JSON {"exit_code": N}


class Shell:
    """Context-managed sandbox shell.

    Each ``run`` call opens a fresh ``/exec`` WebSocket, launches the command
    as an independent child process in the running sandbox container (no TTY,
    no shell chrome unless the caller explicitly wraps in ``sh -c``), and
    returns a :class:`~tilde.models.RunResult` with ``stdout``, ``stderr``,
    and ``exit_code`` on their own channels.

    Usage::

        with repo.shell(image="python:3.12") as sh:
            result = sh.run("echo hello")
            print(result.stdout.text())
            print(result.stderr.text())

    Commands do **not** share shell state (``cd``, exported env vars, aliases
    don't persist across calls).  Callers that need state chain commands
    into one call (``sh.run("cd /foo && ls")``) or pass ``env=``/``cwd=``.

    A clean exit commits the sandbox via ``POST /sandboxes/{id}/finish``;
    an exception rolls it back via ``DELETE /sandboxes/{id}``.
    """

    def __init__(
        self,
        client: Client,
        sandbox: Sandbox,
    ) -> None:
        self._client = client
        self._sandbox = sandbox

    def __repr__(self) -> str:
        return f"Shell(sandbox={self._sandbox.id!r})"

    def __enter__(self) -> Shell:
        self._wait_for_running()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # Clean exit → commit path via /finish; exception → rollback via
        # cancel (DELETE) so accidental failures don't persist changes.
        if exc_type is None:
            self._sandbox.finish()
        else:
            self._sandbox.cancel()

    def run(
        self,
        cmd: str | list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        stdin: bytes | None = None,
        check: bool = False,
    ) -> RunResult:
        """Run ``cmd`` in the sandbox and return stdout, stderr, and exit code.

        Args:
            cmd: Either a shell string (wrapped as ``["sh", "-c", cmd]``) or
                an explicit argv list executed directly without a shell.
            env: Additional environment variables for this exec (merged on top
                of the container environment server-side).
            cwd: Working directory for this exec.
            stdin: Optional bytes to feed to the child's stdin; EOF is sent
                immediately after.  ``None`` means the child inherits a closed
                stdin.
            check: Raise :class:`~tilde.exceptions.CommandError` on non-zero
                exit code.
        """
        if isinstance(cmd, str):
            cmd_list = ["sh", "-c", cmd]
            cmd_str = cmd
        else:
            cmd_list = list(cmd)
            cmd_str = " ".join(cmd_list)

        ws = self._connect_exec_ws()
        try:
            launch: dict[str, Any] = {"cmd": cmd_list}
            if env is not None:
                launch["env"] = env
            if cwd is not None:
                launch["cwd"] = cwd
            ws.send(bytes([_FRAME_LAUNCH]) + json.dumps(launch).encode("utf-8"))

            if stdin is not None:
                if stdin:
                    ws.send(bytes([_FRAME_STDIN]) + stdin)
                ws.send(bytes([_FRAME_STDIN_CLOSE]))

            stdout_buf = bytearray()
            stderr_buf = bytearray()
            exit_code = -1
            deadline = time.monotonic() + _CMD_TIMEOUT

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SandboxError(f"Timeout waiting for command output: {cmd_str}")
                try:
                    frame = ws.recv(timeout=min(remaining, 30.0))
                except TimeoutError:
                    continue
                if not isinstance(frame, bytes) or len(frame) == 0:
                    continue
                frame_type = frame[0]
                payload = frame[1:]
                if frame_type == _FRAME_STDOUT:
                    stdout_buf.extend(payload)
                elif frame_type == _FRAME_STDERR:
                    stderr_buf.extend(payload)
                elif frame_type == _FRAME_EXIT:
                    data = _parse_json_payload(payload)
                    if data is not None:
                        try:
                            exit_code = int(data.get("exit_code", -1))
                        except (TypeError, ValueError):
                            exit_code = -1
                    break
                # Unknown frame types are ignored for forward-compat.
        finally:
            with contextlib.suppress(Exception):
                ws.close()

        result = RunResult(
            stdout=OutputStream(bytes(stdout_buf)),
            stderr=OutputStream(bytes(stderr_buf)),
            exit_code=exit_code,
        )
        if check and exit_code != 0:
            raise CommandError(
                f"Command {cmd_str!r} exited with code {exit_code}",
                result=result,
                command=cmd_str,
            )
        return result

    # -- Internal helpers ----------------------------------------------------

    def _connect_exec_ws(self) -> ClientConnection:
        api_key = self._client._ensure_api_key()
        ws_url = (
            f"{self._client._ws_base_url}"
            f"/organizations/{self._sandbox._org}"
            f"/repositories/{self._sandbox._repo}"
            f"/sandboxes/{self._sandbox.id}/exec"
        )
        return ws_connect(
            ws_url,
            additional_headers={"Authorization": f"Bearer {api_key}"},
        )

    def _wait_for_running(self) -> None:
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


def _parse_json_payload(payload: bytes) -> dict[str, Any] | None:
    """Decode a JSON object payload; return ``None`` on decode failure."""
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None
