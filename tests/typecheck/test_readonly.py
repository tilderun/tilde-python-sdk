"""Type-safety test: Commit objects should NOT have .put() or .delete().

Run with: mypy tests/typecheck/ --strict
Expected: mypy reports attr-defined errors for .put() and .delete() calls.
This file is NOT run by pytest — it is only checked by mypy.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from cerebral.resources.commits import Commit


def check_commit_readonly() -> None:
    client = MagicMock()
    commit = Commit(client, "org", "repo", "abc123")
    commit.objects.put("path", b"data")  # type: ignore[attr-defined]  # should fail
    commit.objects.delete("path")  # type: ignore[attr-defined]  # should fail
