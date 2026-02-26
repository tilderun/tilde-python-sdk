"""Tests for ReadOnlyObjectCollection and SessionObjectCollection."""

import httpx

from cerebral.models import ListingEntry, ObjectMetadata, PutObjectResult


class TestReadOnlyObjectCollection:
    def test_list(self, mock_api, repo):
        """GET .../objects with pagination (no session)."""
        mock_api.get("/organizations/test-org/repositories/test-repo/objects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "path": "file1.txt",
                            "type": "object",
                            "entry": {
                                "address": "addr1",
                                "size": 100,
                                "e_tag": "etag1",
                                "content_type": "text/plain",
                            },
                        },
                        {
                            "path": "file2.csv",
                            "type": "object",
                            "entry": {
                                "address": "addr2",
                                "size": 200,
                                "e_tag": "etag2",
                                "content_type": "text/csv",
                            },
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        from cerebral.resources.objects import ReadOnlyObjectCollection

        objects = ReadOnlyObjectCollection(repo._client, "test-org", "test-repo")
        items = list(objects.list())
        assert len(items) == 2
        assert all(isinstance(i, ListingEntry) for i in items)
        assert items[0].path == "file1.txt"
        assert items[1].path == "file2.csv"

    def test_head(self, mock_api, repo):
        """HEAD .../object?path=foo returns ObjectMetadata from headers."""
        mock_api.head("/organizations/test-org/repositories/test-repo/object").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "etag": '"abc123"',
                    "content-type": "application/octet-stream",
                    "content-length": "1024",
                    "x-cerebral-reproducible": "true",
                },
            )
        )
        from cerebral.resources.objects import ReadOnlyObjectCollection

        objects = ReadOnlyObjectCollection(repo._client, "test-org", "test-repo")
        meta = objects.head("foo")
        assert isinstance(meta, ObjectMetadata)
        assert meta.etag == '"abc123"'
        assert meta.content_type == "application/octet-stream"
        assert meta.content_length == 1024
        assert meta.reproducible is True


class TestSessionObjectCollection:
    def test_list(self, mock_api, repo):
        """GET .../objects?session_id=... with pagination."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-obj-1"})
        )
        mock_api.get("/organizations/test-org/repositories/test-repo/objects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "path": "file1.txt",
                            "type": "object",
                            "entry": {
                                "address": "addr1",
                                "size": 100,
                                "e_tag": "etag1",
                                "content_type": "text/plain",
                            },
                        },
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        session = repo.session()
        items = list(session.objects.list())
        assert len(items) == 1
        assert items[0].path == "file1.txt"

    def test_list_with_prefix_delimiter(self, mock_api, repo):
        """prefix and delimiter params are forwarded."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-obj-2"})
        )
        mock_api.get("/organizations/test-org/repositories/test-repo/objects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"path": "data/", "type": "prefix"},
                    ],
                    "pagination": {"has_more": False, "next_offset": None, "max_per_page": 100},
                },
            )
        )
        session = repo.session()
        items = list(session.objects.list(prefix="data/", delimiter="/"))
        assert len(items) == 1
        assert items[0].path == "data/"
        assert items[0].type == "prefix"

    def test_head(self, mock_api, repo):
        """HEAD .../object?session_id=...&path=foo returns ObjectMetadata."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-obj-3"})
        )
        mock_api.head("/organizations/test-org/repositories/test-repo/object").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "etag": '"abc123"',
                    "content-type": "application/octet-stream",
                    "content-length": "1024",
                    "x-cerebral-reproducible": "true",
                },
            )
        )
        session = repo.session()
        meta = session.objects.head("foo")
        assert isinstance(meta, ObjectMetadata)
        assert meta.etag == '"abc123"'

    def test_put(self, mock_api, repo):
        """Presigned upload: stage → upload to presigned URL → finalize."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-obj-4"})
        )
        # 1. Stage
        stage_route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/object/stage"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "upload_url": "https://s3.example.com/bucket/obj123",
                    "physical_address": "s3://bucket/obj123",
                    "signature": "sig-abc",
                    "expires_at": "2026-02-24T00:00:00Z",
                },
            )
        )
        # 2. Upload to presigned URL
        upload_route = mock_api.put(url="https://s3.example.com/bucket/obj123").mock(
            return_value=httpx.Response(200)
        )
        # 3. Finalize
        finalize_route = mock_api.put(
            "/organizations/test-org/repositories/test-repo/object/finalize"
        ).mock(
            return_value=httpx.Response(
                201,
                json={
                    "path": "foo",
                    "etag": "new-etag",
                },
            )
        )
        session = repo.session()
        result = session.objects.put("foo", b"hello world")
        assert isinstance(result, PutObjectResult)
        assert result.path == "foo"
        assert result.etag == "new-etag"
        assert stage_route.called
        assert upload_route.called
        assert finalize_route.called

    def test_delete(self, mock_api, repo):
        """DELETE .../object?session_id=...&path=foo."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-obj-5"})
        )
        route = mock_api.delete("/organizations/test-org/repositories/test-repo/object").mock(
            return_value=httpx.Response(204)
        )
        session = repo.session()
        session.objects.delete("foo")
        assert route.called

    def test_delete_many(self, mock_api, repo):
        """POST .../objects/delete?session_id=... with list of paths."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-obj-6"})
        )
        route = mock_api.post("/organizations/test-org/repositories/test-repo/objects/delete").mock(
            return_value=httpx.Response(200, json={"deleted": 3})
        )
        session = repo.session()
        count = session.objects.delete_many(["a.txt", "b.txt", "c.txt"])
        assert count == 3
        assert route.called
