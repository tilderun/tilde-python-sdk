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

## Quick Start

```bash
export TILDE_API_KEY="your-api-key"
```

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

### One-shot execution

For a single command that doesn't need an interactive session:

```python
result = repo.execute("python train.py", image="python:3.12")
print(result.stdout.text())

# check=False to handle errors yourself
result = repo.execute("might-fail", check=False)
if result.exit_code != 0:
    print(result.stderr.text())
```

### Output streams

Both `execute()` and `shell.run()` return a `RunResult` whose `stdout` and
`stderr` fields are `OutputStream` objects:

| Method | Returns | Description |
|--------|---------|-------------|
| `.read()` | `bytes` | Full output as raw bytes |
| `.text(encoding='utf-8')` | `str` | Full output decoded as a string |
| `.iter_bytes(chunk_size)` | `Iterator[bytes]` | Yield byte chunks |
| `.iter_text(chunk_size)` | `Iterator[str]` | Yield text chunks |
| `.iter_lines()` | `Iterator[str]` | Yield lines (no trailing newlines) |

## Configuration

| Option | Environment Variable | Default |
|--------|---------------------|---------|
| `api_key` | `TILDE_API_KEY` | *required* |
| `endpoint_url` | `TILDE_ENDPOINT_URL` | `https://tilde.run` |

Resolution order: explicit parameter > environment variable > default.

A missing API key is not an error at construction time; a `ConfigurationError` is raised
when the first request is made.

### Explicit configuration

```python
import tilde

tilde.configure(api_key="your-api-key", endpoint_url="https://custom.endpoint")
repo = tilde.repository("my-org/my-repo")
```

### Explicit client

```python
from tilde import Client

with Client(api_key="your-api-key") as client:
    repo = client.repository("my-org/my-repo")
```

## Usage

### Repositories

```python
repo = tilde.repository("my-org/my-repo")

# Lazy-loaded properties
print(repo.id, repo.description, repo.visibility)

# Update
repo.update(description="New description", visibility="public")

# Delete
repo.delete()
```

### Timeline (Commit History)

```python
for commit in repo.timeline():
    print(commit.id, commit.message)

    # View changes introduced by this commit
    for change in commit.diff():
        print(f"object {change.path} was {change.status} in this commit!")
```

### Organizations

```python
orgs = tilde.Client(api_key="key").organizations

# Create
org = orgs.create("my-org", "My Organization")

# List
for org in orgs.list():
    print(org.name)

# Members
for member in orgs.members("my-org").list():
    print(member.username, member.role)

orgs.members("my-org").add(user_id="user-uuid", role="member")
```

### Agents

Manage agents and their API keys using the fluent organization resource:

```python
org = tilde.organization("my-org")

# Create an agent
agent = org.agents.create("my-agent", description="CI bot", metadata={"env": "prod"})
print(agent.name, agent.id)

# List agents
for agent in org.agents.list():
    print(agent.name)

# Get a specific agent
agent = org.agents.get("my-agent")

# Update an agent
agent = org.agents.update("my-agent", description="Updated description")

# Delete an agent
org.agents.delete("my-agent")
```

#### Agent API Keys

```python
agent = org.agents.get("my-agent")

# Create a key (token is only shown once)
created = agent.api_keys.create("dev-key")
print(created.token)  # cak-... full token

# List keys
for key in agent.api_keys.list():
    print(key.name, key.token_hint)

# Get by ID and revoke a key
key = agent.api_keys.get(key_id)
key.revoke()
```

#### Organization Sub-resources

The organization resource also provides access to repositories, members, groups,
policies, and connectors:

```python
org = tilde.organization("my-org")

for repo in org.repositories.list():
    print(repo.name)

for member in org.members.list():
    print(member.username, member.role)
```

### Groups

```python
groups = client.organizations.groups("my-org")

group = groups.create("engineers", description="Engineering team")
detail = groups.get(group.id)  # includes members and attachments

groups.add_member(group.id, "user", "user-uuid")
groups.remove_member(group.id, "user", "user-uuid")
```

### Policies

```python
policies = client.organizations.policies("my-org")

# Create and validate
result = policies.validate("package tilde.authz\ndefault allow = true")
policy = policies.create("allow-all", rego="...", description="Allow everything")

# Attach/detach
policies.attach(policy.id, "group", "group-uuid")
policies.detach(policy.id, "group", "group-uuid")

# Effective policies for a user
for ep in policies.effective_policies("user-uuid"):
    print(ep.policy_name, ep.source)
```

### Connectors and Imports

```python
# Org-level connectors
connectors = client.organizations.connectors("my-org")
conn = connectors.create("my-s3", "s3", {"bucket": "my-bucket", "region": "us-east-1"})

# Attach to repo
repo.connectors.attach(conn.id)

# Import
job_id = repo.imports.start(
    connector_id=conn.id,
    source_path="s3://my-bucket/data/",
    destination_path="imported/",
)
status = repo.imports.status(job_id)
print(status.status, status.objects_imported)
```

## Advanced Usage

### Sessions

Sessions provide direct transactional access to objects in a repository. They
act like transactions: stage changes, then commit or rollback.

```python
# Context manager (recommended) — rolls back on error
with repo.session() as session:
    objects = session.objects.list(prefix="data/", delimiter="/")
    session.objects.put("data/report.csv", b"content")
    session.commit("update CSV files")

# Explicit control
session = repo.session()
print(session.session_id)
session.objects.put("data/file.csv", b"content")
session.commit("modifying data in parallel")
# or: session.rollback()
```

### Attaching to an Existing Session

Resume a session from another thread, process, or machine:

```python
# In another thread/process/machine:
session = repo.attach(session_id)
session.objects.put("data/file2.csv", b"more content")
session.commit("finishing work")
```

### Objects

```python
with repo.session() as session:
    # Upload
    session.objects.put("data/file.csv", b"content")

    # Download (streaming)
    with session.objects.get("data/file.csv") as f:
        data = f.read()

    # Read a specific byte range (e.g., first 1 KB)
    with session.objects.get("data/file.parquet", byte_range=(0, 1023)) as f:
        header = f.read()

    # Stream large objects without caching
    with session.objects.get("data/large.bin", cache=False) as f:
        for chunk in f.iter_bytes(chunk_size=8192):
            process(chunk)

    # List (auto-paginating, with directory grouping)
    for entry in session.objects.list(prefix="data/", delimiter="/"):
        print(entry.path, entry.type)  # type is "object" or "prefix"

    # Check metadata
    meta = session.objects.head("data/file.csv")
    print(meta.etag, meta.content_type, meta.content_length)

    # Delete
    session.objects.delete("data/file.csv")

    session.commit("object operations")
```

### Uncommitted Changes

```python
session = repo.session()
session.objects.put("data/new.csv", b"content")

for entry in session.uncommitted():
    print(entry.path)
```

## Error Handling

All SDK exceptions inherit from `TildeError`:

```
TildeError                           # base for all SDK errors
+-- ConfigurationError               # missing API key, bad endpoint
+-- TransportError                   # network failures, DNS, timeouts
+-- SerializationError               # invalid JSON in response
+-- APIError                         # base for HTTP API errors
    +-- BadRequestError              # 400
    +-- AuthenticationError          # 401
    +-- ForbiddenError               # 403
    +-- NotFoundError                # 404
    +-- ConflictError                # 409
    +-- GoneError                    # 410
    +-- PreconditionFailedError      # 412
    +-- LockedError                  # 423
    +-- ServerError                  # 5xx
```

`APIError` includes `status_code`, `message`, `code`, `request_id`, `method`, `url`, and
`response_text` for debugging.

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

## Large Object Handling

By default, `objects.get()` caches the full object in memory on `.read()`. For large
objects, disable caching and stream:

```python
with repo.session() as session:
    with session.objects.get("large-file.bin", cache=False) as f:
        for chunk in f.iter_bytes(chunk_size=1024 * 1024):
            output.write(chunk)
```

### Byte Range Requests

Use `byte_range` to read only a portion of an object without downloading the full
content. This is useful for reading file headers, tailing logs, or formats like
Parquet that support random access.

```python
# Read the first 4 bytes (e.g., a magic number)
with repo.objects.get("data/file.parquet", byte_range=(0, 3)) as f:
    magic = f.read()

# Read from offset 1024 to end of file
with repo.objects.get("data/file.parquet", byte_range=(1024, None)) as f:
    tail = f.read()
```

The reader exposes the `content_range` property with the server's `Content-Range`
header value (e.g., `"bytes 0-3/49152"`):

```python
with repo.objects.get("data/file.parquet", byte_range=(0, 1023)) as f:
    data = f.read()
    print(f.content_range)   # "bytes 0-1023/49152"
    print(f.content_length)  # 1024
```

## MCP Server

The SDK includes an [MCP](https://modelcontextprotocol.io/) server that exposes
Tilde operations as tools for AI agents. The API key must be an agent key
(prefix `cak-`).

### Running

```bash
# Via uvx
uvx --from tilde-sdk tilde-mcp

# Or as a Python module
TILDE_API_KEY=cak-... python -m tilde.mcp
```

### Available Tools

| Tool | Description |
|------|-------------|
| `create_session` | Create a new editing session on a repository. |
| `list_objects` | List objects and prefixes with metadata (size, content type, etc.). |
| `head_object` | Get an object's size and content type without downloading it. |
| `get_object` | Download an object's content (UTF-8 text or base64-encoded binary). |
| `put_object` | Upload an object (UTF-8 text or base64-encoded binary). |
| `delete_object` | Delete an object from a session. |
| `commit_session` | Commit a session (returns approval URL if review is required). |
| `close_session` | Roll back and close a session. |

### Configuration

The server reads `TILDE_API_KEY` from the environment on every tool call.
Only agent keys (`cak-` prefix) are accepted.

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
