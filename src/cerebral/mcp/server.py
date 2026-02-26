"""MCP tool definitions for the Cerebral SDK."""

from __future__ import annotations

import base64
import functools
import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from cerebral._version import __version__
from cerebral.client import Client
from cerebral.exceptions import (
    AuthenticationError,
    CerebralError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServerError,
    TransportError,
)

if TYPE_CHECKING:
    from cerebral.resources.sessions import Session

F = TypeVar("F", bound=Callable[..., Any])

mcp = FastMCP("Cerebral")

_lock = threading.Lock()
_client: Client | None = None
_client_key: str | None = None
_client_ua: str | None = None
_sessions: dict[tuple[str, str], Session] = {}


def _validate_agent_key() -> str:
    """Read and validate the API key from the environment.

    Raises :class:`ToolError` when the key is missing or does not carry
    the ``cak-`` agent-key prefix.
    """
    key = os.environ.get("CEREBRAL_API_KEY")
    if not key:
        raise ToolError("CEREBRAL_API_KEY environment variable is not set")
    if not key.startswith("cak-"):
        raise ToolError("CEREBRAL_API_KEY must be an agent key (prefix 'cak-')")
    return key


def _build_mcp_user_agent(ctx: Context) -> str:
    """Build extra User-Agent segments from MCP context."""
    parts = [f"cerebral-mcp/{__version__}"]
    try:
        client_info = ctx.session.client_params.clientInfo  # type: ignore[union-attr]
        if client_info.name:
            parts.append(f"{client_info.name}/{client_info.version}")
    except (AttributeError, TypeError):
        pass
    return " ".join(parts)


def _get_client(api_key: str, extra_user_agent: str | None = None) -> Client:
    """Return (or create) a :class:`Client` for *api_key* and *extra_user_agent*."""
    global _client, _client_key, _client_ua
    with _lock:
        if _client is None or api_key != _client_key or extra_user_agent != _client_ua:
            if _client is not None:
                _client.close()
            _client = Client(api_key=api_key, extra_user_agent=extra_user_agent)
            _client_key = api_key
            _client_ua = extra_user_agent
            _sessions.clear()
        return _client


def _get_configured_client(ctx: Context) -> Client:
    """Validate the agent key, build the UA, and return a :class:`Client`."""
    api_key = _validate_agent_key()
    extra_ua = _build_mcp_user_agent(ctx)
    return _get_client(api_key, extra_user_agent=extra_ua)


def _get_or_attach_session(client: Client, repository: str, session_id: str) -> Session:
    """Look up a cached session or attach to an existing one."""
    key = (repository, session_id)
    with _lock:
        session = _sessions.get(key)
        if session is not None:
            return session
    # Attach outside the lock (no I/O under lock)
    session = client.repository(repository).attach(session_id)
    with _lock:
        _sessions[key] = session
    return session


def _handle_errors(fn: F) -> F:
    """Decorator that maps SDK exceptions to :class:`ToolError`."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except AuthenticationError:
            raise ToolError("Authentication failed. Check your CEREBRAL_API_KEY.") from None
        except ForbiddenError:
            repository = kwargs.get("repository", "")
            raise ToolError(f"Permission denied for {repository}.") from None
        except NotFoundError:
            raise ToolError(f"Not found: {kwargs.get('path', 'resource')}") from None
        except ConflictError as e:
            raise ToolError(f"Conflict: {e}") from None
        except TransportError as e:
            raise ToolError(f"Network error: {e}") from None
        except ServerError as e:
            raise ToolError(f"Server error: {e}") from None
        except CerebralError as e:
            raise ToolError(str(e)) from None

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
@_handle_errors
def list_repositories(organization: str, ctx: Context) -> list[dict[str, Any]]:
    """List repositories in an organization.

    Returns a list of repositories. Each entry has ``id``, ``name``,
    ``description``, ``visibility``, and ``created_at``.

    Args:
        organization: Organization slug.
    """
    client = _get_configured_client(ctx)
    results: list[dict[str, Any]] = []
    for repo in client.organization(organization).repositories.list():
        results.append(
            {
                "id": repo.id,
                "name": repo.name,
                "description": repo.description,
                "visibility": repo.visibility,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
            }
        )
    return results


@mcp.tool()
@_handle_errors
def create_repository(
    organization: str,
    name: str,
    ctx: Context,
    description: str = "",
    visibility: str = "private",
) -> dict[str, Any]:
    """Create a new repository in an organization.

    Args:
        organization: Organization slug.
        name: Repository name.
        description: Optional description.
        visibility: ``"private"`` (default) or ``"public"``.

    Returns:
        A dict with ``id``, ``name``, ``description``, ``visibility``,
        and ``created_at``.
    """
    if visibility not in ("private", "public"):
        raise ToolError("visibility must be 'private' or 'public'")
    client = _get_configured_client(ctx)
    repo = client.organization(organization).repositories.create(
        name, description=description, visibility=visibility
    )
    return {
        "id": repo.id,
        "name": repo.name,
        "description": repo.description,
        "visibility": repo.visibility,
        "created_at": repo.created_at.isoformat() if repo.created_at else None,
    }


@mcp.tool()
@_handle_errors
def create_session(repository: str, ctx: Context) -> dict[str, str]:
    """Create a new editing session on a Cerebral repository.

    Args:
        repository: Repository path in ``"org/repo"`` format.

    Returns:
        A dict with ``session_id`` and ``repository``.
    """
    client = _get_configured_client(ctx)
    session = client.repository(repository).session()
    with _lock:
        _sessions[(repository, session.session_id)] = session
    return {"session_id": session.session_id, "repository": repository}


@mcp.tool()
@_handle_errors
def list_objects(
    repository: str,
    session_id: str,
    ctx: Context,
    prefix: str = "",
    delimiter: str = "/",
    amount: int = 100,
) -> list[dict[str, Any]]:
    """List objects and prefixes in a session.

    Returns a list of entries. Each entry has ``path`` and ``type``.

    Entries with ``type="prefix"`` represent directory-like groupings
    and only contain ``path`` and ``type``.

    Entries with ``type="object"`` represent files and include full
    metadata:
    - ``size``: file size in bytes (int or null).
    - ``last_modified``: ISO 8601 timestamp of last modification (str or null).
    - ``content_type``: MIME type, e.g. ``"text/csv"`` (str or null).
    - ``metadata``: user-defined key-value pairs (dict).
    - ``source_metadata``: import origin info (dict or null) with fields
      ``connector_id``, ``connector_type``, ``source_path``,
      ``version_id``, ``source_etag``, ``import_time``,
      ``import_job_id``, ``reproducible``.

    To get the size of a specific object, either use this listing
    (check the ``size`` field) or call ``head_object`` for a single path.

    Args:
        repository: Repository path in ``"org/repo"`` format.
        session_id: Session ID.
        prefix: Filter by key prefix.
        delimiter: Directory grouping delimiter.
        amount: Maximum number of items to return.
    """
    if amount <= 0:
        raise ToolError("amount must be a positive integer")
    client = _get_configured_client(ctx)
    session = _get_or_attach_session(client, repository, session_id)
    iterator = session.objects.list(
        prefix=prefix or None,
        delimiter=delimiter or None,
    )
    results: list[dict[str, Any]] = []
    for listing_entry in iterator:
        item: dict[str, Any] = {"path": listing_entry.path, "type": listing_entry.type}
        entry = listing_entry.entry
        if entry is not None:
            item["size"] = entry.size
            item["last_modified"] = entry.last_modified.isoformat() if entry.last_modified else None
            item["content_type"] = entry.content_type or None
            item["metadata"] = entry.metadata
            sm = entry.source_metadata
            if sm is not None:
                item["source_metadata"] = {
                    "connector_id": sm.connector_id,
                    "connector_type": sm.connector_type,
                    "source_path": sm.source_path,
                    "version_id": sm.version_id,
                    "source_etag": sm.source_etag,
                    "import_time": sm.import_time.isoformat() if sm.import_time else None,
                    "import_job_id": sm.import_job_id,
                    "reproducible": sm.reproducible,
                }
            else:
                item["source_metadata"] = None
        results.append(item)
        if len(results) >= amount:
            break
    return results


@mcp.tool()
@_handle_errors
def get_object(repository: str, session_id: str, path: str, ctx: Context) -> dict[str, str]:
    """Read an object's content from a session.

    Args:
        repository: Repository path in ``"org/repo"`` format.
        session_id: Session ID.
        path: Object path.

    Returns:
        A dict with ``path``, ``encoding`` (``"utf-8"`` or ``"base64"``),
        ``content_type``, and ``content``.
    """
    client = _get_configured_client(ctx)
    session = _get_or_attach_session(client, repository, session_id)
    reader = session.objects.get(path)
    raw = reader.read()
    content_type_header = reader.content_type
    try:
        text = raw.decode("utf-8")
        return {
            "path": path,
            "encoding": "utf-8",
            "content_type": content_type_header or "text/plain; charset=utf-8",
            "content": text,
        }
    except UnicodeDecodeError:
        return {
            "path": path,
            "encoding": "base64",
            "content_type": content_type_header or "application/octet-stream",
            "content": base64.b64encode(raw).decode("ascii"),
        }


@mcp.tool()
@_handle_errors
def head_object(repository: str, session_id: str, path: str, ctx: Context) -> dict[str, Any]:
    """Get metadata for a single object without downloading its content.

    Returns a dict with:
    - ``path``: the requested object path.
    - ``content_type``: MIME type, e.g. ``"text/csv"`` (str or null).
    - ``size``: file size in bytes (int or null).

    Use this to check an object's size or type before deciding whether
    to download it with ``get_object``.

    Args:
        repository: Repository path in ``"org/repo"`` format.
        session_id: Session ID.
        path: Object path.
    """
    client = _get_configured_client(ctx)
    session = _get_or_attach_session(client, repository, session_id)
    meta = session.objects.head(path)
    return {
        "path": path,
        "content_type": meta.content_type,
        "size": meta.content_length,
    }


@mcp.tool()
@_handle_errors
def put_object(
    repository: str,
    session_id: str,
    path: str,
    content: str,
    ctx: Context,
    encoding: str = "utf-8",
) -> dict[str, str]:
    """Upload an object into a session.

    Args:
        repository: Repository path in ``"org/repo"`` format.
        session_id: Session ID.
        path: Object path.
        content: Object content (text or base64-encoded).
        encoding: ``"utf-8"`` (default) or ``"base64"``.

    Returns:
        A dict with ``path`` and ``etag``.
    """
    if encoding not in ("utf-8", "base64"):
        raise ToolError("encoding must be 'utf-8' or 'base64'")
    client = _get_configured_client(ctx)
    session = _get_or_attach_session(client, repository, session_id)
    data = base64.b64decode(content) if encoding == "base64" else content.encode("utf-8")
    result = session.objects.put(path, data)
    return {"path": result.path, "etag": result.etag}


@mcp.tool()
@_handle_errors
def delete_object(repository: str, session_id: str, path: str, ctx: Context) -> dict[str, str]:
    """Delete an object from a session.

    Args:
        repository: Repository path in ``"org/repo"`` format.
        session_id: Session ID.
        path: Object path.

    Returns:
        A dict with ``status`` and ``path``.
    """
    client = _get_configured_client(ctx)
    session = _get_or_attach_session(client, repository, session_id)
    session.objects.delete(path)
    return {"status": "deleted", "path": path}


@mcp.tool()
@_handle_errors
def commit_session(
    repository: str,
    session_id: str,
    message: str,
    ctx: Context,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Commit a session.

    Args:
        repository: Repository path in ``"org/repo"`` format.
        session_id: Session ID.
        message: Commit message.
        metadata: Optional key-value metadata to attach to the commit.

    Returns:
        A dict with ``status`` (``"committed"`` or ``"approval_required"``),
        ``commit_id``, and ``web_url``.
    """
    client = _get_configured_client(ctx)
    session = _get_or_attach_session(client, repository, session_id)
    result = session.commit_result(message, metadata=metadata)
    with _lock:
        _sessions.pop((repository, session_id), None)
    return {
        "status": result.status,
        "commit_id": result.commit_id,
        "web_url": result.web_url,
    }


@mcp.tool()
@_handle_errors
def close_session(repository: str, session_id: str, ctx: Context) -> dict[str, str]:
    """Roll back and close a session.

    Args:
        repository: Repository path in ``"org/repo"`` format.
        session_id: Session ID.

    Returns:
        A dict with ``status`` (``"rolled_back"`` or ``"already_closed"``)
        and ``session_id``.
    """
    client = _get_configured_client(ctx)
    session = _get_or_attach_session(client, repository, session_id)
    try:
        session.rollback()
    except (NotFoundError, ConflictError):
        with _lock:
            _sessions.pop((repository, session_id), None)
        return {"status": "already_closed", "session_id": session_id}
    with _lock:
        _sessions.pop((repository, session_id), None)
    return {"status": "rolled_back", "session_id": session_id}
