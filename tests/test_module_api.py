"""Tests for the module-level API (tilde package)."""


class TestModuleAPI:
    def test_version(self):
        """tilde.__version__ is a string."""
        import tilde

        assert isinstance(tilde.__version__, str)
        assert len(tilde.__version__) > 0

    def test_configure_and_repository(self):
        """tilde.configure() then tilde.repository() returns a Repository."""
        import tilde
        from tilde.resources.repositories import Repository

        # Reset default client
        tilde._default_client = None

        tilde.configure(api_key="test-key-module")
        repo = tilde.repository("my-org/my-repo")
        assert isinstance(repo, Repository)

        # Cleanup
        if tilde._default_client is not None:
            tilde._default_client.close()
            tilde._default_client = None

    def test_default_client_created_lazily(self):
        """Default client is created lazily on first use."""
        import tilde

        # Reset default client
        tilde._default_client = None

        assert tilde._default_client is None

        # Calling _get_default_client should create one
        client = tilde._get_default_client()
        assert client is not None
        assert tilde._default_client is client

        # Cleanup
        tilde._default_client.close()
        tilde._default_client = None

    def test_exception_exports(self):
        """All exception classes are importable from tilde."""
        from tilde import (
            APIError,
            AuthenticationError,
            BadRequestError,
            ConfigurationError,
            ConflictError,
            ForbiddenError,
            GoneError,
            LockedError,
            NotFoundError,
            PreconditionFailedError,
            SerializationError,
            ServerError,
            TildeError,
            TransportError,
        )

        assert issubclass(ConfigurationError, TildeError)
        assert issubclass(TransportError, TildeError)
        assert issubclass(SerializationError, TildeError)
        assert issubclass(APIError, TildeError)
        assert issubclass(BadRequestError, APIError)
        assert issubclass(AuthenticationError, APIError)
        assert issubclass(ForbiddenError, APIError)
        assert issubclass(NotFoundError, APIError)
        assert issubclass(ConflictError, APIError)
        assert issubclass(GoneError, APIError)
        assert issubclass(PreconditionFailedError, APIError)
        assert issubclass(LockedError, APIError)
        assert issubclass(ServerError, APIError)

    def test_model_exports(self):
        """Key models are importable from tilde."""
        from tilde import (
            CommitData,
            ImportJob,
            Organization,
        )

        # Spot-check a few are actual types
        assert isinstance(Organization.__name__, str)
        assert isinstance(CommitData.__name__, str)
        assert isinstance(ImportJob.__name__, str)
