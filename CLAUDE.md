# Cerebral Python SDK

Python SDK for the Cerebral data versioning API (`https://cerebral.storage`).

## Project Layout

```
src/cerebral/           # Package source
  __init__.py           # Public exports + module-level API (configure, repository, organizations)
  client.py             # HTTP client wrapping httpx (lazy init, context manager)
  models.py             # Dataclass models (slots=True) with from_dict() classmethods
  exceptions.py         # Exception hierarchy: CerebralError → APIError → status-specific errors
  _config.py            # Config resolution (env vars: CEREBRAL_API_KEY, CEREBRAL_ENDPOINT_URL)
  _version.py           # Single source of truth for version string
  _pagination.py        # Offset-based PaginatedIterator (generic, TypeVar-based)
  _object_reader.py     # Streaming file-like reader with optional caching
  resources/            # Resource classes for each API domain
    repositories.py     # Repository resource
    sessions.py         # Session resource (transactional put/get/delete + commit/rollback)
    objects.py          # ReadOnlyObjectCollection + SessionObjectCollection
    commits.py          # Commit timeline and diffs
    organizations.py    # Org CRUD + membership
    groups.py           # Group management
    policies.py         # Rego policy validation and attachment
    connectors.py       # S3 and other connectors
    imports.py          # Import job queuing and status
  mcp/                  # MCP server for AI agents
    __init__.py         # Exports mcp (FastMCP instance) and main()
    __main__.py         # python -m cerebral.mcp entry point
    server.py           # Tool definitions, key validation, session caching, error mapping

tests/                  # pytest + respx (HTTP mocking)
  conftest.py           # Fixtures: mock_api, client, repo
  test_*.py             # One test file per module
  typecheck/            # mypy strict-mode type assertions

docs/                   # MkDocs (material theme) documentation
openapi.yaml            # OpenAPI spec for the Cerebral API
```

## Key Architecture Details

- **HTTP layer**: `Client` wraps `httpx.Client` with lazy initialization and proper cleanup via context manager. Methods: `_get`, `_post`, `_put`, `_delete`, `_head`, `_stream`, plus `_*_json` convenience variants.
- **Resources**: Each API domain has a resource class. The `Client` creates resources; resources hold a back-reference to the client for HTTP calls.
- **Sessions**: Transactional model — `repo.session()` returns a context manager that auto-rolls back on exception. Supports `commit(message)` and `rollback()`.
- **Pagination**: Generic `PaginatedIterator[T]` using offset-based `after` cursor, default page size 100.
- **Models**: Frozen `@dataclass(slots=True)` with `from_dict()` classmethods. ISO 8601 datetime parsing via `_parse_dt()`.
- **Errors**: `CerebralError` base → `APIError` (HTTP 400+) → status-specific subclasses (401, 403, 404, 409, 410, 412, 423, 5xx). Also `ConfigurationError`, `TransportError`, `SerializationError`.
- **MCP server** (`src/cerebral/mcp/`): Built on `fastmcp`. Exposes SDK operations as MCP tools for AI agents. Key details:
  - Requires agent keys (`cak-` prefix) — validated on every tool call via `CEREBRAL_API_KEY` env var.
  - Thread-safe client and session caching (module-level `_lock`, `_client`, `_sessions`). Key rotation recreates the client and clears cached sessions.
  - `_handle_errors` decorator maps SDK exceptions → `ToolError` with clean messages.
  - `Session.commit_result()` returns a `CommitResult` dataclass (non-blocking, no warnings) used by the `commit_session` tool.
  - Tools: `create_session`, `list_objects`, `head_object`, `get_object`, `put_object`, `delete_object`, `commit_session`, `close_session`.
  - Entry point: `cerebral-mcp` console script (`uvx --from cerebral-sdk cerebral-mcp`) or `python -m cerebral.mcp`.

## Commands

### Install dependencies
```
uv sync --all-extras
```

### Run tests
```
uv run pytest
```

### Run tests with coverage
```
uv run pytest --cov=cerebral --cov-report=term-missing
```

### Lint
```
uv run ruff check src/ tests/
```

### Format check
```
uv run ruff format --check src/ tests/
```

### Auto-format
```
uv run ruff format src/ tests/
```

### Type check
```
uv run mypy src/cerebral/
uv run mypy tests/typecheck/ --strict
```

### Build
```
uv build
```

Output goes to `dist/` (wheel + sdist).

### Publish
```
uv publish
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`:
- Tests against Python 3.11, 3.12, 3.13
- Lint → format check → mypy (src) → mypy (typecheck) → pytest with coverage

## API Coverage Notes

- The OAuth2 endpoints in `openapi.yaml` (`/auth/oauth/*`) are browser-based flows and do **not** need to be implemented in the SDK.

## Code Style

- **Ruff** with line-length 100, target Python 3.11
- Rule sets: E, F, I, UP, B, SIM, TCH, RUF
- **mypy** strict mode enabled
- All public types are re-exported from `cerebral.__init__`
