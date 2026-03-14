"""HTTP client for the Tilde API."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import httpx

from tilde._config import resolve_config
from tilde._version import __version__
from tilde.exceptions import (
    ConfigurationError,
    SerializationError,
    TransportError,
    api_error_for_status,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tilde.resources.organizations import OrganizationCollection, OrgResource
    from tilde.resources.repositories import Repository


class Client:
    """Tilde API client.

    Args:
        endpoint_url: Override the API endpoint (default: env or
            ``https://tilde.run``).
        api_key: API key.  Falls back to ``TILDE_API_KEY`` env var.
            May be ``None`` at construction; raises
            :class:`~tilde.exceptions.ConfigurationError` at request time.
        extra_user_agent: Additional User-Agent segments appended after the
            SDK identifier (e.g. ``"tilde-mcp/0.1.0 claude-desktop/1.2"``).
        httpx_client: Optional pre-configured ``httpx.Client`` for testing.
    """

    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        api_key: str | None = None,
        extra_user_agent: str | None = None,
        httpx_client: httpx.Client | None = None,
    ) -> None:
        self._config = resolve_config(endpoint_url=endpoint_url, api_key=api_key)
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
            )
            self._owns_http = True

    # -- HTTP helpers --------------------------------------------------------

    def _ensure_api_key(self) -> str:
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
        """Get a :class:`~tilde.resources.repositories.Repository` resource.

        Args:
            repo_path: Repository path in ``"org/repo"`` format.
        """
        from tilde.resources.repositories import Repository

        parts = repo_path.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid repository path {repo_path!r}: expected 'org/repo' format")
        return Repository(self, parts[0], parts[1])

    def organization(self, org: str) -> OrgResource:
        """Get an :class:`~tilde.resources.organizations.OrgResource` for fluent access."""
        from tilde.resources.organizations import OrgResource

        return OrgResource(self, org)

    @property
    def organizations(self) -> OrganizationCollection:
        """Access the organizations API."""
        from tilde.resources.organizations import OrganizationCollection

        return OrganizationCollection(self)

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
