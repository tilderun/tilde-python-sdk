"""Tests for the tilde._config module."""

from tilde._config import resolve_config

DEFAULT_ENDPOINT = "https://tilde.run"


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    """When nothing is provided, sensible defaults are used."""

    def test_default_endpoint_url(self, monkeypatch):
        monkeypatch.delenv("TILDE_ENDPOINT_URL", raising=False)
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        cfg = resolve_config()
        assert cfg.endpoint_url == DEFAULT_ENDPOINT

    def test_api_key_defaults_to_none(self, monkeypatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        monkeypatch.delenv("TILDE_ENDPOINT_URL", raising=False)
        cfg = resolve_config()
        assert cfg.api_key is None


# ---------------------------------------------------------------------------
# Environment variable resolution
# ---------------------------------------------------------------------------


class TestEnvVarResolution:
    """Environment variables override defaults."""

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("TILDE_API_KEY", "env-key-123")
        monkeypatch.delenv("TILDE_ENDPOINT_URL", raising=False)
        cfg = resolve_config()
        assert cfg.api_key == "env-key-123"

    def test_endpoint_url_from_env(self, monkeypatch):
        monkeypatch.setenv("TILDE_ENDPOINT_URL", "https://custom.endpoint.io")
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        cfg = resolve_config()
        assert cfg.endpoint_url == "https://custom.endpoint.io"


# ---------------------------------------------------------------------------
# Explicit parameter resolution (highest priority)
# ---------------------------------------------------------------------------


class TestExplicitParamResolution:
    """Explicit keyword arguments beat both env vars and defaults."""

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("TILDE_API_KEY", "env-key")
        cfg = resolve_config(api_key="explicit-key")
        assert cfg.api_key == "explicit-key"

    def test_explicit_endpoint_overrides_env(self, monkeypatch):
        monkeypatch.setenv("TILDE_ENDPOINT_URL", "https://env.endpoint.io")
        cfg = resolve_config(endpoint_url="https://explicit.endpoint.io")
        assert cfg.endpoint_url == "https://explicit.endpoint.io"

    def test_explicit_params_override_defaults(self, monkeypatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        monkeypatch.delenv("TILDE_ENDPOINT_URL", raising=False)
        cfg = resolve_config(
            api_key="my-key",
            endpoint_url="https://my.endpoint.io",
        )
        assert cfg.api_key == "my-key"
        assert cfg.endpoint_url == "https://my.endpoint.io"


# ---------------------------------------------------------------------------
# base_url property
# ---------------------------------------------------------------------------


class TestBaseUrl:
    """base_url is derived from endpoint_url with /api/v1 appended."""

    def test_base_url_appends_api_v1(self, monkeypatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        monkeypatch.delenv("TILDE_ENDPOINT_URL", raising=False)
        cfg = resolve_config(endpoint_url="https://api.tilde.run")
        assert cfg.base_url == "https://api.tilde.run/api/v1"

    def test_base_url_strips_trailing_slash(self, monkeypatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        monkeypatch.delenv("TILDE_ENDPOINT_URL", raising=False)
        cfg = resolve_config(endpoint_url="https://api.tilde.run/")
        assert cfg.base_url == "https://api.tilde.run/api/v1"

    def test_base_url_strips_multiple_trailing_slashes(self, monkeypatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        monkeypatch.delenv("TILDE_ENDPOINT_URL", raising=False)
        cfg = resolve_config(endpoint_url="https://api.tilde.run///")
        # Should at minimum not end with a slash before /api/v1
        assert "/api/v1" in cfg.base_url
        assert cfg.base_url.endswith("/api/v1")

    def test_default_base_url(self, monkeypatch):
        monkeypatch.delenv("TILDE_API_KEY", raising=False)
        monkeypatch.delenv("TILDE_ENDPOINT_URL", raising=False)
        cfg = resolve_config()
        assert cfg.base_url == f"{DEFAULT_ENDPOINT}/api/v1"
