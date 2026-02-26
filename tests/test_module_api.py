"""Tests for the module-level API (cerebral package)."""


class TestModuleAPI:
    def test_version(self):
        """cerebral.__version__ is a string."""
        import cerebral

        assert isinstance(cerebral.__version__, str)
        assert len(cerebral.__version__) > 0

    def test_configure_and_repository(self):
        """cerebral.configure() then cerebral.repository() returns a Repository."""
        import cerebral
        from cerebral.resources.repositories import Repository

        # Reset default client
        cerebral._default_client = None

        cerebral.configure(api_key="test-key-module")
        repo = cerebral.repository("my-org/my-repo")
        assert isinstance(repo, Repository)

        # Cleanup
        if cerebral._default_client is not None:
            cerebral._default_client.close()
            cerebral._default_client = None

    def test_default_client_created_lazily(self):
        """Default client is created lazily on first use."""
        import cerebral

        # Reset default client
        cerebral._default_client = None

        assert cerebral._default_client is None

        # Calling _get_default_client should create one
        client = cerebral._get_default_client()
        assert client is not None
        assert cerebral._default_client is client

        # Cleanup
        cerebral._default_client.close()
        cerebral._default_client = None

    def test_exception_exports(self):
        """All exception classes are importable from cerebral."""
        from cerebral import (
            APIError,
            AuthenticationError,
            BadRequestError,
            CerebralError,
            ConfigurationError,
            ConflictError,
            ForbiddenError,
            GoneError,
            LockedError,
            NotFoundError,
            PreconditionFailedError,
            SerializationError,
            ServerError,
            TransportError,
        )

        assert issubclass(ConfigurationError, CerebralError)
        assert issubclass(TransportError, CerebralError)
        assert issubclass(SerializationError, CerebralError)
        assert issubclass(APIError, CerebralError)
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
        """Key models are importable from cerebral."""
        from cerebral import (
            CommitData,
            ImportJob,
            Organization,
        )

        # Spot-check a few are actual types
        assert isinstance(Organization.__name__, str)
        assert isinstance(CommitData.__name__, str)
        assert isinstance(ImportJob.__name__, str)
