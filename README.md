# Cerebral Python SDK

Python SDK for the [Cerebral](https://cerebral.storage) data versioning API.

## Installation

```bash
pip install cerebral-sdk
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add cerebral-sdk
```

## Quick Start

### Using environment variables (simplest)

```bash
export CEREBRAL_API_KEY="your-api-key"
```

```python
import cerebral

repo = cerebral.repository("my-org/my-repo")
print(repo.description)  # lazy-loaded on first access

with repo.session() as session:
    session.objects.put("data/example.csv", b"col1,col2\na,b\n")
    session.commit("added example csv")
```

### Explicit configuration

```python
import cerebral

cerebral.configure(api_key="your-api-key", endpoint_url="https://custom.endpoint")
repo = cerebral.repository("my-org/my-repo")
```

### Explicit client (most flexible)

```python
from cerebral import Client

with Client(api_key="your-api-key") as client:
    repo = client.repository("my-org/my-repo")
    with repo.session() as session:
        session.objects.put("data/file.csv", b"content")
        session.commit("update data")
```

## Configuration

| Option | Environment Variable | Default |
|--------|---------------------|---------|
| `api_key` | `CEREBRAL_API_KEY` | *required* |
| `endpoint_url` | `CEREBRAL_ENDPOINT_URL` | `https://cerebral.storage` |

Resolution order: explicit parameter > environment variable > default.

A missing API key is not an error at construction time; a `ConfigurationError` is raised
when the first request is made.

## Usage

### Repositories

```python
repo = cerebral.repository("my-org/my-repo")

# Lazy-loaded properties
print(repo.id, repo.description, repo.visibility)

# Update
repo.update(description="New description", visibility="public")

# Delete
repo.delete()
```

### Sessions

Sessions are the primary way to read and write objects. They act like transactions:
stage changes, then commit or rollback.

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
orgs = cerebral.Client(api_key="key").organizations

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
org = cerebral.organization("my-org")

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
org = cerebral.organization("my-org")

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
result = policies.validate("package cerebral.authz\ndefault allow = true")
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

## Error Handling

All SDK exceptions inherit from `CerebralError`:

```
CerebralError                        # base for all SDK errors
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
from cerebral import NotFoundError, CerebralError

try:
    with repo.session() as session:
        with session.objects.get("nonexistent") as f:
            f.read()
except NotFoundError as e:
    print(f"Not found: {e.message} (request_id={e.request_id})")
except CerebralError as e:
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

## MCP Server

The SDK includes an [MCP](https://modelcontextprotocol.io/) server that exposes
Cerebral operations as tools for AI agents. The API key must be an agent key
(prefix `cak-`).

### Running

```bash
# Via uvx
uvx --from cerebral-sdk cerebral-mcp

# Or as a Python module
CEREBRAL_API_KEY=cak-... python -m cerebral.mcp
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

The server reads `CEREBRAL_API_KEY` from the environment on every tool call.
Only agent keys (`cak-` prefix) are accepted.

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
uv run mypy src/cerebral/

# Build
uv build
```

## License

Apache 2.0
