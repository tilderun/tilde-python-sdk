# Contributing to Tilde Python SDK

Thank you for your interest in contributing! This document explains how to get
started.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
git clone https://github.com/tilderun/tilde-python-sdk.git
cd tilde-python-sdk
uv sync --all-extras
```

Install pre-commit hooks:

```bash
uv run pre-commit install
```

## Development workflow

### Run tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=tilde --cov-report=term-missing
```

### Lint and format

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Auto-fix lint issues:

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

### Type check

```bash
uv run mypy src/tilde/
uv run mypy tests/typecheck/ --strict
```

## Code style

- **Ruff** with line-length 100, target Python 3.11
- **mypy** strict mode enabled
- All public types are re-exported from `tilde.__init__`
- Models use `@dataclass(slots=True)` with `from_dict()` classmethods
- Tests use pytest with respx for HTTP mocking

## Pre-commit hooks

The project uses pre-commit hooks for:

- **ruff** - linting and auto-fix
- **ruff-format** - code formatting
- **detect-secrets** - secret scanning

These run automatically on `git commit` after installing hooks. They also run in
CI on every push and pull request.

## Submitting changes

1. Fork the repository and create a branch from `main`.
2. Make your changes and add tests.
3. Ensure all checks pass: `uv run pytest`, `uv run ruff check src/ tests/`,
   `uv run ruff format --check src/ tests/`, and `uv run mypy src/tilde/`.
4. Open a pull request against `main`.

## License

By contributing, you agree that your contributions will be licensed under the
Apache License 2.0. See [LICENSE](LICENSE) for details.
