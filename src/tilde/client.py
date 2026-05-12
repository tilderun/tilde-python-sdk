"""HTTP client for the Tilde API."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import httpx

from tilde._config import resolve_config
from tilde._credentials import (
    ENV_SANDBOX_CREDENTIALS_URI,
    SandboxCredentialsProvider,
)
from tilde._version import __version__
from tilde.exceptions import (
    ConfigurationError,
    SerializationError,
    TransportError,
    api_error_for_status,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tilde.resources.organizations import Organizations
    from tilde.resources.repositories import Repository


class Client:
    """Tilde API client.

    Args:
        endpoint_url: Override the API endpoint (default: env or
            ``https://tilde.run``).
        api_key: API key.  Falls back to ``TILDE_API_KEY`` env var.
            May be ``None`` at construction; raises
            :class:`~tilde.exceptions.ConfigurationError` at request time.
        credentials_provider: Dynamic credentials source (e.g.
            :class:`~tilde._credentials.SandboxCredentialsProvider`).  When
            provided, its token is used instead of ``api_key`` for outgoing
            requests.  If omitted and no static API key is configured
            (``api_key`` param, ``TILDE_API_KEY``, or ``~/.tilde/config.yaml``),
            the client auto-detects ``TILDE_SANDBOX_CREDENTIALS_URI`` and
            instantiates a sandbox IMDS provider.  A static key always wins
            over auto-detection so it is not silently overridden.
        extra_user_agent: Additional User-Agent segments appended after the
            SDK identifier (e.g. ``"my-app/0.1.0 claude-desktop/1.2"``).
        httpx_client: Optional pre-configured ``httpx.Client`` for testing.
    """

    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        api_key: str | None = None,
        default_sandbox_image: str | None = None,
        credentials_provider: SandboxCredentialsProvider | None = None,
        extra_user_agent: str | None = None,
        httpx_client: httpx.Client | None = None,
    ) -> None:
        self._config = resolve_config(
            endpoint_url=endpoint_url,
            api_key=api_key,
            default_sandbox_image=default_sandbox_image,
        )
        self._credentials_provider = _resolve_credentials_provider(
            explicit_provider=credentials_provider,
            explicit_api_key=api_key,
            config_api_key=self._config.api_key,
        )
        self._multipart_unsupported = False
        if httpx_client is not None:
            self._http = httpx_client
            self._owns_http = False
        else:
            ua = f"tilde-python-sdk/{__version__}"
            if extra_user_agent:
                ua = f"{ua} {extra_user_agent}"
            self._http = httpx.Client(
                base_url=self._config.base_url,
                headers={"User-Agent": ua},
                timeout=httpx.Timeout(30.0),
            )
            self._owns_http = True

    @property
    def _ws_base_url(self) -> str:
        """WebSocket base URL (``https`` → ``wss``, ``http`` → ``ws``)."""
        url = self._config.base_url
        if url.startswith("https://"):
            return "wss://" + url[len("https://") :]
        if url.startswith("http://"):
            return "ws://" + url[len("http://") :]
        return url

    # -- HTTP helpers --------------------------------------------------------

    def _ensure_api_key(self) -> str:
        if self._credentials_provider is not None:
            return self._credentials_provider.get_token()
        if self._config.api_key is None:
            raise ConfigurationError(
                "No API key configured. Set TILDE_API_KEY or pass api_key= to Client()."
            )
        return self._config.api_key

    def _auth_headers(self) -> dict[str, str]:
        api_key = self._ensure_api_key()
        return {"Authorization": f"Bearer {api_key}"}

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        method = response.request.method
        url = str(response.request.url)
        response_text = response.text
        message = ""
        code = ""
        request_id = ""
        try:
            body = response.json()
            message = body.get("message", "")
            code = body.get("code", "")
            request_id = body.get("request_id", "")
        except Exception:
            message = response_text[:200]
        raise api_error_for_status(
            response.status_code,
            message=message,
            code=code,
            request_id=request_id,
            method=method,
            url=url,
            response_text=response_text,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._auth_headers(), **kwargs.pop("headers", {})}
        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.TransportError as exc:
            raise TransportError(f"Request failed: {exc}", cause=exc) from exc
        self._raise_for_status(response)
        return response

    def _get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("POST", path, **kwargs)

    def _put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("PUT", path, **kwargs)

    def _delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("DELETE", path, **kwargs)

    def _head(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("HEAD", path, **kwargs)

    def _patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("PATCH", path, **kwargs)

    @contextmanager
    def _stream(self, method: str, path: str, **kwargs: Any) -> Iterator[httpx.Response]:
        headers = {**self._auth_headers(), **kwargs.pop("headers", {})}
        try:
            with self._http.stream(method, path, headers=headers, **kwargs) as response:
                if not response.is_success:
                    response.read()
                    self._raise_for_status(response)
                yield response
        except httpx.TransportError as exc:
            raise TransportError(f"Request failed: {exc}", cause=exc) from exc

    def _get_json(self, path: str, **kwargs: Any) -> Any:
        """GET and parse JSON response."""
        response = self._get(path, **kwargs)
        try:
            return response.json()
        except Exception as exc:
            raise SerializationError(f"Invalid JSON in response: {exc}") from exc

    def _post_json(self, path: str, **kwargs: Any) -> Any:
        """POST and parse JSON response."""
        response = self._post(path, **kwargs)
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except Exception as exc:
            raise SerializationError(f"Invalid JSON in response: {exc}") from exc

    def _patch_json(self, path: str, **kwargs: Any) -> Any:
        """PATCH and parse JSON response."""
        response = self._patch(path, **kwargs)
        try:
            return response.json()
        except Exception as exc:
            raise SerializationError(f"Invalid JSON in response: {exc}") from exc

    def _put_json(self, path: str, **kwargs: Any) -> Any:
        """PUT and parse JSON response."""
        response = self._put(path, **kwargs)
        try:
            return response.json()
        except Exception as exc:
            raise SerializationError(f"Invalid JSON in response: {exc}") from exc

    # -- Resource access -----------------------------------------------------

    def repository(self, repo_path: str) -> Repository:
        """Return a :class:`~tilde.resources.repositories.Repository` for *repo_path*.

        ``tilde.repository('org/repo')`` is the only shorthand in the SDK —
        every other entity is reached through the ``organizations`` chain
        (``client.organizations.get('org').repositories.get('repo')``).

        Args:
            repo_path: Repository path in ``"org/repo"`` format.
        """
        from tilde.resources.repositories import Repository

        parts = repo_path.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid repository path {repo_path!r}: expected 'org/repo' format")
        return Repository(self, parts[0], parts[1])

    @property
    def organizations(self) -> Organizations:
        """The :class:`~tilde.resources.organizations.Organizations` collection."""
        from tilde.resources.organizations import Organizations

        return Organizations(self)

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_http:
            self._http.close()
        if self._credentials_provider is not None:
            self._credentials_provider.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _resolve_credentials_provider(
    *,
    explicit_provider: SandboxCredentialsProvider | None,
    explicit_api_key: str | None,
    config_api_key: str | None,
) -> SandboxCredentialsProvider | None:
    """Pick the credentials provider to use for a new client.

    Precedence: an explicit provider always wins; otherwise any statically
    configured ``api_key`` (explicit ``Client(api_key=...)``, ``TILDE_API_KEY``,
    or ``~/.tilde/config.yaml``) suppresses auto-detection.  This matches the
    principle that credentials set deliberately by the caller should not be
    silently overridden by the sandbox IMDS env var.  Only when no static key
    is available does ``TILDE_SANDBOX_CREDENTIALS_URI`` kick in.
    """
    if explicit_provider is not None:
        return explicit_provider
    if explicit_api_key is not None or config_api_key is not None:
        return None
    uri = os.environ.get(ENV_SANDBOX_CREDENTIALS_URI)
    if uri:
        return SandboxCredentialsProvider(uri)
    return None
