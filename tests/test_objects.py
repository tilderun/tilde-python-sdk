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

    def test_put_small_uses_single_upload(self, mock_api, repo):
        """Data < 64 MB uses stage/finalize (single presigned upload)."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-obj-4"})
        )
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
        upload_route = mock_api.put(url="https://s3.example.com/bucket/obj123").mock(
            return_value=httpx.Response(200)
        )
        finalize_route = mock_api.put(
            "/organizations/test-org/repositories/test-repo/object/finalize"
        ).mock(
            return_value=httpx.Response(
                201,
                json={"path": "foo", "etag": "new-etag"},
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

    def test_put_defaults_to_multipart(self, mock_api, repo):
        """Data >= 64 MB or unknown size triggers multipart flow."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-mp-1"})
        )
        # Initiate multipart
        initiate_route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/object/multipart"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "upload_id": "mp-upload-1",
                    "physical_address": "s3://bucket/mp-obj",
                    "token": "mp-token-1",
                    "expires_at": "2026-02-24T00:00:00Z",
                },
            )
        )
        # Part presigned URL redirect
        mock_api.get("/organizations/test-org/repositories/test-repo/object/multipart/part").mock(
            return_value=httpx.Response(
                307,
                headers={"Location": "https://s3.example.com/bucket/mp-obj?partNumber=1"},
            )
        )
        # Part upload
        part_upload_route = mock_api.put(
            url="https://s3.example.com/bucket/mp-obj?partNumber=1"
        ).mock(return_value=httpx.Response(200, headers={"ETag": '"part-etag-1"'}))
        # Complete
        complete_route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/object/multipart/complete"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"path": "bigfile.bin", "etag": "final-etag"},
            )
        )

        session = repo.session()
        # Use an iterable (unknown size) to force multipart
        result = session.objects.put("bigfile.bin", iter([b"chunk1", b"chunk2"]))
        assert isinstance(result, PutObjectResult)
        assert result.path == "bigfile.bin"
        assert result.etag == "final-etag"
        assert initiate_route.called
        assert part_upload_route.called
        assert complete_route.called

    def test_put_multipart_501_fallback(self, mock_api, repo):
        """Server returns 501 for multipart → falls back to single upload."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-mp-2"})
        )
        # Multipart initiate returns 501
        mock_api.post("/organizations/test-org/repositories/test-repo/object/multipart").mock(
            return_value=httpx.Response(501, json={"message": "Multipart not supported"})
        )
        # Fallback: stage/finalize
        stage_route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/object/stage"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "upload_url": "https://s3.example.com/bucket/fallback",
                    "physical_address": "s3://bucket/fallback",
                    "signature": "sig-fallback",
                    "expires_at": "2026-02-24T00:00:00Z",
                },
            )
        )
        mock_api.put(url="https://s3.example.com/bucket/fallback").mock(
            return_value=httpx.Response(200)
        )
        mock_api.put("/organizations/test-org/repositories/test-repo/object/finalize").mock(
            return_value=httpx.Response(201, json={"path": "bigfile.bin", "etag": "fallback-etag"})
        )

        session = repo.session()
        # Use an iterable to trigger multipart attempt
        result = session.objects.put("bigfile.bin", iter([b"data"]))
        assert result.etag == "fallback-etag"
        assert stage_route.called

        # Verify the flag was cached — subsequent puts skip multipart
        assert repo._client._multipart_unsupported is True

    def test_put_multipart_abort_on_failure(self, mock_api, repo):
        """If part upload fails, abort is called and error re-raised."""
        mock_api.post("/organizations/test-org/repositories/test-repo/sessions").mock(
            return_value=httpx.Response(201, json={"session_id": "sess-mp-3"})
        )
        mock_api.post("/organizations/test-org/repositories/test-repo/object/multipart").mock(
            return_value=httpx.Response(
                200,
                json={
                    "upload_id": "mp-upload-fail",
                    "physical_address": "s3://bucket/mp-fail",
                    "token": "mp-token-fail",
                    "expires_at": "2026-02-24T00:00:00Z",
                },
            )
        )
        # Part redirect succeeds
        mock_api.get("/organizations/test-org/repositories/test-repo/object/multipart/part").mock(
            return_value=httpx.Response(
                307,
                headers={"Location": "https://s3.example.com/bucket/mp-fail?partNumber=1"},
            )
        )
        # Part upload fails
        mock_api.put(url="https://s3.example.com/bucket/mp-fail?partNumber=1").mock(
            return_value=httpx.Response(500)
        )
        # Abort should be called
        abort_route = mock_api.post(
            "/organizations/test-org/repositories/test-repo/object/multipart/abort"
        ).mock(return_value=httpx.Response(204))

        session = repo.session()
        try:
            session.objects.put("bigfile.bin", iter([b"data"]))
            raise AssertionError("Should have raised")
        except AssertionError:
            raise
        except Exception:
            pass
        assert abort_route.called

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
