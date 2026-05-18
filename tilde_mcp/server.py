"""Tilde MCP Server — exposes Tilde SDK operations as MCP tools."""

import os
from typing import Optional

import tilde
import tilde.exceptions as te
from mcp.server.fastmcp import FastMCP

TILDE_API_KEY = os.environ["TILDE_API_KEY"]
tilde.configure(api_key=TILDE_API_KEY)

mcp = FastMCP("tilde")

TERMINAL_IMPORT = {"completed", "failed", "cancelled"}


# ── helpers ──────────────────────────────────────────────────────────────────

def _err(e: te.TildeError) -> dict:
    d = {"error": str(e), "error_type": type(e).__name__}
    if isinstance(e, te.APIError):
        d["status_code"] = str(e.status_code)
    return d


def _drain(paginator, limit: int = 500) -> list:
    result = []
    for i, item in enumerate(paginator):
        if i >= limit:
            break
        result.append(item)
    return result




# ── organisation / repo ──────────────────────────────────────────────────────

@mcp.tool()
def list_repos(org: str) -> dict:
    """List repositories in a Tilde organization."""
    try:
        o = tilde.organizations.get(org)
        repos = _drain(o.repositories.list())
        return {"repos": [{"name": r.name, "visibility": r.visibility,
                           "description": r.description} for r in repos]}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def list_connectors(org: str) -> dict:
    """List connectors in a Tilde organization."""
    try:
        o = tilde.organizations.get(org)
        connectors = _drain(o.connectors.list())
        return {"connectors": [{"id": c.id, "name": c.name, "type": c.type,
                                "source_uri": c.source_uri,
                                "disabled": c.disabled} for c in connectors]}
    except te.TildeError as e:
        return _err(e)


# ── objects ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_objects(repo: str, prefix: Optional[str] = None, limit: int = 500) -> dict:
    """List objects in a repo at HEAD. prefix filters by path prefix."""
    try:
        r = tilde.repository(repo)
        with r.session() as session:
            entries = _drain(session.objects.list(prefix=prefix, amount=limit), limit=limit)
        return {"objects": [{"path": e.path, "type": e.type,
                             "size": e.entry.size if e.entry else None,
                             "etag": e.entry.e_tag if e.entry else None}
                            for e in entries if e.path]}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def read_object(repo: str, path: str) -> dict:
    """Read file content from a repo at HEAD. Returns utf-8 text or base64 for binary."""
    try:
        r = tilde.repository(repo)
        with r.session() as session:
            raw = session.objects.get(path).read()
        try:
            return {"path": path, "content": raw.decode("utf-8"), "encoding": "utf-8",
                    "size": len(raw)}
        except UnicodeDecodeError:
            import base64
            return {"path": path, "content": base64.b64encode(raw).decode("ascii"),
                    "encoding": "base64", "size": len(raw)}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def write_objects(repo: str, files: dict, message: str) -> dict:
    """Write one or more files to a repo and commit. files is {path: text_content}."""
    try:
        r = tilde.repository(repo)
        with r.session() as session:
            for path, content in files.items():
                data = content.encode("utf-8") if isinstance(content, str) else content
                session.objects.put(path, data)
            commit_id = session.commit(message)
        return {"status": "committed", "commit_id": commit_id or "",
                "files_written": list(files.keys())}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def delete_objects(repo: str, paths: list, message: str) -> dict:
    """Delete one or more files from a repo and commit."""
    try:
        r = tilde.repository(repo)
        with r.session() as session:
            for path in paths:
                session.objects.delete(path)
            commit_id = session.commit(message)
        return {"status": "committed", "commit_id": commit_id or "",
                "files_deleted": paths}
    except te.TildeError as e:
        return _err(e)


# ── commits ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_commits(repo: str, amount: int = 20) -> dict:
    """List recent commits in a repo, newest first."""
    try:
        r = tilde.repository(repo)
        commits = _drain(r.commits.list(amount=amount), limit=amount)
        return {"commits": [{"id": c.id, "message": c.message,
                             "committer": c.committer,
                             "date": c.creation_date.isoformat() if c.creation_date else None,
                             "object_count": c.object_count,
                             "total_size": c.total_size} for c in commits]}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def get_commit(repo: str, commit_id: str) -> dict:
    """Get details of a specific commit."""
    try:
        r = tilde.repository(repo)
        c = r.commits.get(commit_id)
        return {"id": c.id, "message": c.message, "committer": c.committer,
                "committer_type": c.committer_type,
                "date": c.creation_date.isoformat() if c.creation_date else None,
                "parents": c.parents, "object_count": c.object_count,
                "total_size": c.total_size, "metadata": c.metadata}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def commit_diff(repo: str, commit_id: str, prefix: Optional[str] = None,
                limit: int = 200) -> dict:
    """List files changed in a commit vs its parent."""
    try:
        r = tilde.repository(repo)
        c = r.commits.get(commit_id)
        entries = _drain(c.diff(prefix=prefix, amount=limit), limit=limit)
        return {"commit_id": commit_id,
                "changes": [{"path": e.path, "type": e.type,
                             "size": e.entry.size if e.entry else None}
                            for e in entries if e.path]}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def revert_commit(repo: str, commit_id: str, message: Optional[str] = None) -> dict:
    """Revert a repo to a previous commit state. Creates a new commit."""
    try:
        r = tilde.repository(repo)
        c = r.commits.get(commit_id)
        new_commit = c.revert(message=message)
        return {"status": "reverted", "new_commit_id": new_commit.id,
                "reverted_to": commit_id}
    except te.TildeError as e:
        return _err(e)


# ── imports ───────────────────────────────────────────────────────────────────

@mcp.tool()
def import_from_connector(repo: str, connector_id: str, destination_path: str,
                          source_prefix: Optional[str] = None) -> dict:
    """Start an import job from a connector. Non-blocking — poll with get_import_job."""
    try:
        r = tilde.repository(repo)
        job = r.imports.create_from_connector(
            connector_id=connector_id,
            destination_path=destination_path,
            source_prefix=source_prefix,
        )
        return {"job_id": job.id, "status": job.status,
                "destination_path": job.destination_path}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def get_import_job(repo: str, job_id: str) -> dict:
    """Poll the status of an import job."""
    try:
        r = tilde.repository(repo)
        job = r.imports.get(job_id)
        return {"job_id": job.id, "status": job.status,
                "objects_imported": job.objects_imported,
                "commit_id": job.commit_id, "error": job.error,
                "destination_path": job.destination_path}
    except te.TildeError as e:
        return _err(e)


# ── sandboxes ─────────────────────────────────────────────────────────────────

TERMINAL_SANDBOX = {"done", "committed", "failed", "cancelled", "error"}


@mcp.tool()
def exec_sandbox(repo: str, command: str, image: Optional[str] = None,
                 env: Optional[dict] = None, timeout_seconds: int = 300) -> dict:
    """Run a shell command in a sandbox and return stdout/exit_code. Blocks until done."""
    import time
    try:
        r = tilde.repository(repo)
        cmd = ["sh", "-c", command]
        sandbox = r.sandboxes.create(image=image or "ubuntu:22.04", command=cmd,
                                     env=env, timeout_seconds=timeout_seconds)
        deadline = time.monotonic() + timeout_seconds
        status = None
        while time.monotonic() < deadline:
            status = sandbox.status()
            if status.state in TERMINAL_SANDBOX:
                break
            time.sleep(2)
        else:
            return {"error": f"Sandbox timed out after {timeout_seconds}s",
                    "sandbox_id": sandbox.id}

        logs = ""
        try:
            with status.stdout() as stream:
                logs = "\n".join(stream)
        except Exception:
            pass
        return {"stdout": logs, "exit_code": status.exit_code,
                "state": status.state, "sandbox_id": sandbox.id}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def create_sandbox(repo: str, image: str, command: Optional[list] = None,
                   env: Optional[dict] = None,
                   timeout_seconds: Optional[int] = None) -> dict:
    """Create a detached sandbox. Returns sandbox_id to poll with get_sandbox_status."""
    try:
        r = tilde.repository(repo)
        sandbox = r.sandboxes.create(image=image, command=command, env=env,
                                     timeout_seconds=timeout_seconds)
        return {"sandbox_id": sandbox.id, "repo": repo}
    except te.TildeError as e:
        return _err(e)


@mcp.tool()
def get_sandbox_status(repo: str, sandbox_id: str) -> dict:
    """Get the status of a sandbox."""
    try:
        r = tilde.repository(repo)
        sandbox = r.sandboxes.get(sandbox_id)
        status = sandbox.status()
        return {"sandbox_id": sandbox_id, "state": status.state,
                "exit_code": status.exit_code, "commit_id": status.commit_id,
                "web_url": status.web_url, "error_message": status.error_message}
    except te.TildeError as e:
        return _err(e)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
