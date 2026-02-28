"""Tests for Commit resource and repo.timeline()."""

import httpx

from cerebral.models import CommitData, ListingEntry
from cerebral.resources.commits import Commit
from cerebral.resources.objects import ReadOnlyObjectCollection

COMMIT_JSON = {
    "id": "abc123",
    "committer": "user-1",
    "committer_type": "user",
    "committer_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "message": "initial commit",
    "meta_range_id": "mr-001",
    "creation_date": "2025-07-01T08:30:00Z",
    "parents": ["parent1", "parent2"],
    "metadata": {"key": "value"},
    "object_count": 42,
    "total_size": 123456,
    "is_stale": False,
}


class TestTimeline:
    def test_timeline(self, mock_api, repo):
        """repo.timeline() returns paginated CommitData."""
        mock_api.get("/organizations/test-org/repositories/test-repo/log").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "c1",
                            "committer": "user-1",
                            "message": "commit 1",
                            "meta_range_id": "mr1",
                            "creation_date": "2025-05-01T10:00:00Z",
                            "parents": [],
                            "metadata": {},
                        },
                        {
                            "id": "c2",
                            "committer": "user-2",
                            "message": "commit 2",
                            "meta_range_id": "mr2",
                            "creation_date": "2025-05-02T10:00:00Z",
                            "parents": ["c1"],
                            "metadata": {},
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        commits = list(repo.timeline())
        assert len(commits) == 2
        assert all(isinstance(c, CommitData) for c in commits)
        assert commits[0].id == "c1"
        assert commits[1].id == "c2"


class TestCommit:
    def test_properties(self, mock_api, repo):
        """All lazy-loaded properties are populated correctly."""
        mock_api.get("/organizations/test-org/repositories/test-repo/commits/abc123").mock(
            return_value=httpx.Response(200, json=COMMIT_JSON)
        )
        commit = Commit(repo._client, "test-org", "test-repo", "abc123")
        assert commit.id == "abc123"
        assert commit.committer == "user-1"
        assert commit.committer_type == "user"
        assert commit.committer_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert commit.message == "initial commit"
        assert commit.creation_date is not None
        assert commit.creation_date.year == 2025
        assert commit.parents == ["parent1", "parent2"]
        assert commit.metadata == {"key": "value"}
        assert commit.meta_range_id == "mr-001"
        assert commit.object_count == 42
        assert commit.total_size == 123456
        assert commit.is_stale is False

    def test_objects_readonly(self, mock_api, repo):
        """Commit.objects returns ReadOnlyObjectCollection."""
        commit = Commit(repo._client, "test-org", "test-repo", "abc123")
        objects = commit.objects
        assert isinstance(objects, ReadOnlyObjectCollection)

    def test_revert(self, mock_api, repo):
        """commit.revert() POSTs to .../commits/{id}/revert and returns a new Commit."""
        mock_api.get("/organizations/test-org/repositories/test-repo/commits/abc123").mock(
            return_value=httpx.Response(200, json=COMMIT_JSON)
        )
        mock_api.post(
            "/organizations/test-org/repositories/test-repo/commits/abc123/revert"
        ).mock(return_value=httpx.Response(201, json={"commit_id": "revert-1"}))
        commit = Commit(repo._client, "test-org", "test-repo", "abc123")
        reverted = commit.revert(message="undo change", metadata={"reason": "bug"})
        assert isinstance(reverted, Commit)
        assert reverted.id == "revert-1"

    def test_revert_default_message(self, mock_api, repo):
        """commit.revert() with no arguments sends empty body."""
        route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/commits/abc123/revert"
        ).mock(return_value=httpx.Response(201, json={"commit_id": "revert-2"}))
        commit = Commit(repo._client, "test-org", "test-repo", "abc123")
        reverted = commit.revert()
        assert reverted.id == "revert-2"
        assert route.called

    def test_diff(self, mock_api, repo):
        """commit.diff() diffs this commit against its first parent."""
        mock_api.get("/organizations/test-org/repositories/test-repo/commits/abc123").mock(
            return_value=httpx.Response(200, json=COMMIT_JSON)
        )
        mock_api.get("/organizations/test-org/repositories/test-repo/diff").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "path": "changed.txt",
                            "type": "object",
                            "status": "modified",
                            "entry": {
                                "address": "addr1",
                                "size": 100,
                                "e_tag": "etag1",
                                "content_type": "text/plain",
                            },
                        },
                        {
                            "path": "new.txt",
                            "type": "object",
                            "status": "added",
                            "entry": {
                                "address": "addr2",
                                "size": 50,
                                "e_tag": "etag2",
                                "content_type": "text/plain",
                            },
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        commit = Commit(repo._client, "test-org", "test-repo", "abc123")
        items = list(commit.diff())
        assert len(items) == 2
        assert all(isinstance(i, ListingEntry) for i in items)
        assert items[0].path == "changed.txt"
        assert items[0].status == "modified"
        assert items[1].path == "new.txt"
        assert items[1].status == "added"
