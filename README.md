# Tilde Python SDK

Python SDK for the [Tilde](https://tilde.run) data versioning API.

## Installation

```bash
pip install tilde-sdk
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add tilde-sdk
```

Requires Python 3.11+.

## Quick Start

```python
import tilde

repo = tilde.repository("my-org/my-repo")

# Run commands in an interactive sandbox
with repo.shell(image="python:3.12") as sh:
    sh.run("pip install pandas")
    result = sh.run("python train.py")
    print(result.stdout.text())

    # Stream output line by line
    result = sh.run("cat /sandbox/results.csv")
    for line in result.stdout.iter_lines():
        print(line)
```

> [!IMPORTANT]
> **Transactional by default.** All filesystem modifications made in a sandbox
> happen in the context of a transactional session. If anything fails midway or
> is aborted, changes don't take effect. Only successful sandboxes' changes are
> committed atomically to the repository -- so your data is always in a
> consistent state. See [Sessions](#sessions) for more details.

## Authentication

The SDK resolves credentials in this order (first match wins):

1. **Explicit parameter** — `Client(api_key=...)` or `tilde.configure(api_key=...)`.
2. **Environment variable** — `TILDE_API_KEY`.
3. **CLI config file** — `~/.tilde/config.yaml` (written by `tilde auth login`).
4. **Sandbox metadata endpoint** — `TILDE_SANDBOX_CREDENTIALS_URI` (auto-detected
   only when no static key is configured; injected by the sandbox runtime for code
   running *inside* a Tilde sandbox).

A static key always wins over sandbox auto-detection, so credentials set
deliberately by the caller are never silently overridden.

### Using the CLI's saved credentials

After `tilde auth login`, the SDK picks up the credentials automatically — no
env var or in-code configuration needed:

```python
import tilde

repo = tilde.repository("my-org/my-repo")
```

### Environment variables

Right for CI/CD, agent workflows, and Docker containers where the CLI hasn't run:

```bash
export TILDE_API_KEY="your-api-key"
export TILDE_ENDPOINT_URL="https://tilde.run"  # optional
```

### Module-level configuration

```python
import tilde

tilde.configure(api_key="your-api-key")
repo = tilde.repository("my-org/my-repo")
```

### Explicit client

Use an explicit client when you need multiple configurations or full control
over the HTTP lifecycle:

```python
from tilde import Client

with Client(api_key="your-api-key") as client:
    repo = client.repository("my-org/my-repo")
```

A missing API key is not an error at construction time; a `ConfigurationError`
is raised when the first request is made.

### Configuration reference

| Option | Environment variable | Default |
|--------|---------------------|---------|
| `api_key` | `TILDE_API_KEY` | *required* |
| `endpoint_url` | `TILDE_ENDPOINT_URL` | `https://tilde.run` |
| `default_sandbox_image` | `TILDE_DEFAULT_SANDBOX_IMAGE` | `ubuntu:22.04` |

## Sandbox Execution

The fastest way to run code against your repository data. Sandboxes execute
inside isolated containers with your data mounted as a volume — every change is
captured as a transaction.

### Interactive shell

Use `repo.shell()` to run multiple commands in a single sandbox:

```python
with repo.shell(image="python:3.12") as sh:
    sh.run("pip install pandas")
    result = sh.run("python train.py")
    print(result.stdout.text())
    print(result.stderr.text())
```

The shell is a context manager — on clean exit changes commit automatically,
on exception they roll back. Each `sh.run()` spawns an independent child
process: shell state (`cd`, exported vars, aliases) does **not** persist across
calls. Chain commands in one call (`sh.run("cd /foo && ls")`) or pass `env=` /
`cwd=` to `run()`.

`shell.run()` returns a `RunResult` with `stdout`, `stderr`, and `exit_code`.
Pass `check=True` to raise `CommandError` on non-zero exits.

### One-shot execution

For a single command that doesn't need an interactive session:

```python
result = repo.execute("python train.py", image="python:3.12")
print(result.stdout.text())

# check=False to handle errors yourself
result = repo.execute("might-fail", image="python:3.12", check=False)
if result.exit_code != 0:
    print(result.stdout.text())
```

### Output streams

`RunResult.stdout` and `RunResult.stderr` are `OutputStream` instances:

| Method | Returns | Description |
|--------|---------|-------------|
| `.read()` | `bytes` | Full output as raw bytes |
| `.text(encoding='utf-8')` | `str` | Full output decoded as a string |
| `.iter_bytes(chunk_size)` | `Iterator[bytes]` | Yield byte chunks |
| `.iter_text(chunk_size)` | `Iterator[str]` | Yield text chunks |
| `.iter_lines()` | `Iterator[str]` | Yield lines (no trailing newlines) |

## Repositories

```python
import tilde

# Shorthand: the only top-level shortcut in the SDK
repo = tilde.repository("my-org/my-repo")

# Lazy-loaded properties
print(repo.id, repo.description, repo.visibility)

# Update
repo.update(description="New description", visibility="public")

# Delete (soft delete)
repo.delete()
```

Create a repository through its organization:

```python
org = tilde.organizations.get("my-org")
repo = org.repositories.create(
    "my-repo",
    description="My dataset",
    session_max_duration_days=7,
    retention_days=90,
)

for r in org.repositories.list():
    print(r.name, r.description)
```

## Commits

```python
# Newest first, auto-paginating
for commit in repo.commits.list():
    print(commit.id, commit.committer, commit.message)

# Cap results
for commit in repo.commits.list(amount=10):
    print(commit.id)

# Look up by ID
commit = repo.commits.get("a1b2c3d4e5f6")

# Diff introduced by a commit
for change in commit.diff():
    print(change.status, change.path)

# Revert
revert = commit.revert(message="undo")
```

## Pagination

Every `.list()` returns a `PaginatedIterator` that fetches pages lazily. Two
keyword arguments tune iteration:

| Argument | Effect |
|---|---|
| `amount` | Cap on the **total** number of results yielded. |
| `page_size` | Number of results per **HTTP page** (default 100, server max 1000). |

```python
for entry in commit.objects.list(prefix="data/", page_size=500):
    process(entry)
```

## Sessions

Sessions provide direct transactional access to objects. Prefer sandbox
execution for running code; sessions are for fine-grained object operations
from your own process.

```python
# Context manager — rolls back on error
with repo.session() as session:
    session.objects.put("data/report.csv", b"content")
    session.objects.delete("data/old.csv")
    session.commit("update CSV files")

# Explicit control
session = repo.session()
print(session.session_id)
session.objects.put("data/file.csv", b"content")
session.commit("modifying data")
# or: session.rollback()
```

Resume a session from another thread, process, or machine:

```python
session = repo.attach(session_id)
session.objects.put("data/file2.csv", b"more content")
session.commit("finishing work")
```

## Objects

### Writing

```python
import pathlib

with repo.session() as session:
    # From bytes
    session.objects.put("data/hello.txt", b"Hello, Tilde!")

    # From a file
    with open("dataset.parquet", "rb") as f:
        session.objects.put("data/dataset.parquet", f)

    # From a Path (opened/closed automatically)
    session.objects.put("data/model.bin", pathlib.Path("model.bin"))

    # Server-side copy (no download/upload)
    session.objects.copy("data/hello.txt", "data/hello-backup.txt")

    # Delete
    session.objects.delete("data/old.csv")
    session.objects.delete_many(["data/a.csv", "data/b.csv"])

    session.commit("upload files")
```

Files ≥ 64 MB automatically use multipart upload; smaller files use a single
presigned PUT. No code changes needed.

### Reading

Objects can be read from a committed snapshot (via a `Commit`) or from within a
session (including uncommitted staged changes):

```python
# From a commit
commit = next(iter(repo.commits.list()))
with commit.objects.get("data/hello.txt") as f:
    print(f.read().decode())

# Within a session
with repo.session() as session:
    with session.objects.get("data/file.csv") as f:
        data = f.read()

    # Metadata only
    meta = session.objects.head("data/file.csv")
    print(meta.etag, meta.content_type, meta.content_length)
```

### Streaming and byte ranges

Large objects: disable caching and stream in chunks:

```python
with commit.objects.get("data/large.bin", cache=False) as f:
    for chunk in f.iter_bytes(chunk_size=1024 * 1024):
        output.write(chunk)
```

Byte ranges work for file headers, log tails, or columnar formats like Parquet:

```python
# First 4 bytes
with commit.objects.get("data/file.parquet", byte_range=(0, 3)) as f:
    magic = f.read()

# From offset 1024 to end
with commit.objects.get("data/file.parquet", byte_range=(1024, None)) as f:
    tail = f.read()
    print(f.content_range)   # "bytes 1024-49151/49152"
    print(f.content_length)  # bytes returned
```

### Listing

```python
for entry in commit.objects.list(prefix="data/", delimiter="/"):
    print(entry.path, entry.type)  # "object" or "prefix"
```

### Uncommitted changes

```python
session = repo.session()
session.objects.put("data/new.csv", b"content")
for entry in session.uncommitted():
    print(entry.path)
```

## Organizations

```python
import tilde

# Create, list, get, delete at the module level
org = tilde.organizations.create("my-org", display_name="My Org")
for o in tilde.organizations.list():
    print(o.name, o.display_name)
org = tilde.organizations.get("my-org")
tilde.organizations.delete("my-org")
```

An `Organization` exposes every org-scoped sub-resource as a property:

```python
org = tilde.organizations.get("my-org")
org.repositories
org.members
org.agents
org.roles
org.groups
org.policies
org.connectors
```

### Members

```python
for m in org.members.list():
    print(m.username, m.email)

org.members.create("alice")          # add by username
org.members.delete("user-uuid")      # remove by user_id
```

### Groups

```python
groups = org.groups

group = groups.create("engineers", description="Engineering team")
group = groups.get(group.id)                                # includes members + attachments
group.members.create(subject_type="user", subject_id="user-uuid")
group.members.delete(subject_type="user", subject_id="user-uuid")
group.update(name="engineering", description="Updated")
group.delete()

# Effective groups for a principal
for g in groups.effective(principal_type="user", principal_id="user-uuid"):
    print(g.group_name, g.source)
```

### Policies

```python
policies = org.policies

# Validate before creating
result = policies.validate("GetObject()")
print(result.valid, result.errors)

policy = policies.create(
    name="read-only",
    policy_text="ListRepositories()\nGetRepository()\nGetObject()\n",
    description="Read-only access",
)

# Generate from natural language
text = policies.generate("Allow read-only access to all repositories")

# Attach / detach
policy.attach(principal_type="group", principal_id="group-uuid")
policy.detach(principal_type="group", principal_id="group-uuid")

# Effective policies for a principal
for ep in policies.effective(principal_type="user", principal_id="user-uuid"):
    print(ep.policy_name, ep.source)
```

### Roles and Agents

Non-human identities authenticated via API keys:
- **Roles** (`trk-` prefix) — CI/CD pipelines, automation without metadata.
- **Agents** (`tak-` prefix) — automated tools and AI assistants, with metadata
  and optional inline policies.

```python
# Roles
role = org.roles.create("ci-deployer", description="CI/CD pipeline")
for role in org.roles.list():
    print(role.name)

# Agents
agent = org.agents.create(
    "data-pipeline",
    description="Nightly pipeline",
    metadata={"env": "prod"},
)
agent.update(metadata={"env": "staging"})
agent.update(inline_policy="ListRepositories()\nGetObject()\n")
```

#### API keys

```python
agent = org.agents.get("data-pipeline")

# Create a key (the full token is only shown once)
created = agent.api_keys.create("pipeline-key")
print(created.token)              # tak-...

for key in agent.api_keys.list():
    print(key.name, key.token_hint)

key = agent.api_keys.get(key_id)
key.revoke()
```

The same `api_keys` collection exists on `Role` instances (tokens prefixed
`trk-`).

## Secrets

Encrypted key-value pairs injected as environment variables into sandboxes.

```python
# Repository-scoped
repo.secrets.create("API_KEY", "sk-abc123...")
secret = repo.secrets.get("API_KEY")
print(secret.value)
repo.secrets.delete("API_KEY")

# Agent-scoped (override repo secrets with the same key)
agent = org.agents.get("data-pipeline")
agent.secrets.create("OPENAI_KEY", "sk-abc123...")
```

Precedence at sandbox launch (highest to lowest):
1. `env=` passed in the sandbox request
2. Agent secrets (if running as an agent)
3. Repository secrets

## Connectors and Imports

```python
connectors = org.connectors

# S3
conn = connectors.create(
    name="production-s3",
    type="s3",
    source_uri="s3://my-bucket/datasets/",
    config={
        "access_key_id": "AKIA...",
        "secret_access_key": "...",
        "region": "us-west-2",
    },
)

# Attach to a repo
repo.connectors.attach(conn.id)
for c in repo.connectors.list():
    print(c.name, c.type)
```

Import from a connector:

```python
import time

job = repo.imports.create_from_connector(
    connector_id=conn.id,
    destination_path="imported/",
    source_prefix="datasets/",
    commit_message="Import production datasets",
)

while job.status not in ("completed", "failed"):
    time.sleep(2)
    job.refresh()
    print(job.status, job.objects_imported)

if job.status == "completed":
    print(f"Import done! Commit: {job.commit_id}")
```

Cross-repository imports copy data from one Tilde repo to another:

```python
job = repo.imports.create_from_repository(
    repo_path="other-org/source-data",
    destination_path="external/",
    source_prefix="datasets/train/",
    commit_message="Import training data",
)
```

## Agent Approval Workflow

When a repository requires approval for agent commits, `session.commit()`
blocks by default until a human approves or rolls back. The approval URL is
emitted as a `UserWarning`.

```python
with repo.session() as session:
    session.objects.put("data/results.csv", b"col1,col2\na,b\n")
    session.commit("add results")  # blocks until approved
```

Non-blocking:

```python
result = session.commit("add results", block_for_approval=False)
# result is None; session stays open for review
```

Structured result (no blocking, no warnings):

```python
result = session.commit_result("add results")
if result.status == "committed":
    print(result.commit_id)
elif result.status == "approval_required":
    print(result.web_url)
```

## Low-Level Sandboxes and Triggers

`repo.shell()` and `repo.execute()` cover most needs. For direct control over
async lifecycle, triggers, and delegation, use `repo.sandboxes` and
`repo.sandbox_triggers`. See the
[full docs](https://docs.tilde.run/python-sdk/) for details.

## Error Handling

All SDK exceptions inherit from `TildeError`:

```
TildeError                           # base for all SDK errors
├── ConfigurationError               # missing API key, bad endpoint
├── TransportError                   # network failures, DNS, timeouts
├── SerializationError               # invalid JSON in response
├── SandboxError                     # sandbox lifecycle failure
├── CommandError                     # non-zero exit (repo.execute / shell.run(check=True))
└── APIError                         # base for HTTP API errors
    ├── BadRequestError              # 400
    ├── AuthenticationError          # 401
    ├── ForbiddenError               # 403
    ├── NotFoundError                # 404
    ├── ConflictError                # 409
    ├── GoneError                    # 410
    ├── PreconditionFailedError      # 412
    ├── LockedError                  # 423
    └── ServerError                  # 5xx
```

`APIError` carries `status_code`, `message`, `code`, `request_id`, `method`,
`url`, and `response_text`.

```python
from tilde import NotFoundError, TildeError

try:
    with repo.session() as session:
        with session.objects.get("nonexistent") as f:
            f.read()
except NotFoundError as e:
    print(f"Not found: {e.message} (request_id={e.request_id})")
except TildeError as e:
    print(f"SDK error: {e}")
```

## Documentation

Full documentation is available at <https://docs.tilde.run/python-sdk/>.

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint and format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/tilde/

# Build
uv build
```

## License

Apache 2.0
