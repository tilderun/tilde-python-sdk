"""Cerebral Python SDK.

Quick start::

    import cerebral

    repo = cerebral.repository('my-org/repo1')

    with repo.session() as session:
        session.objects.put('foo/bar.csv', b'data')
        session.commit('update data')
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cerebral._version import __version__
from cerebral.client import Client
from cerebral.exceptions import (
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
from cerebral.models import (
    Agent,
    APIKey,
    APIKeyCreated,
    AttachmentRecord,
    CommitData,
    CommitResult,
    ConnectorInfo,
    EffectiveGroup,
    EffectivePolicy,
    Entry,
    EntryRecord,
    Group,
    GroupDetail,
    GroupMember,
    ImportJob,
    ListingEntry,
    Membership,
    ObjectMetadata,
    Organization,
    OrgSummary,
    Policy,
    PolicyDetail,
    PolicySummary,
    PutObjectResult,
    RepositoryData,
    RepositoryWithOrg,
    Role,
    SourceMetadata,
    ValidationError,
    ValidationResult,
)

if TYPE_CHECKING:
    from cerebral.resources.organizations import OrganizationCollection, OrgResource
    from cerebral.resources.repositories import Repository

__all__ = [
    "APIError",
    "APIKey",
    "APIKeyCreated",
    "Agent",
    "AttachmentRecord",
    "AuthenticationError",
    "BadRequestError",
    # Exceptions
    "CerebralError",
    "Client",
    "CommitData",
    "CommitResult",
    "ConfigurationError",
    "ConflictError",
    "ConnectorInfo",
    "EffectiveGroup",
    "EffectivePolicy",
    "Entry",
    "EntryRecord",
    "ForbiddenError",
    "GoneError",
    "Group",
    "GroupDetail",
    "GroupMember",
    "ImportJob",
    "ListingEntry",
    "LockedError",
    "Membership",
    "NotFoundError",
    "ObjectMetadata",
    "OrgSummary",
    # Models
    "Organization",
    "Policy",
    "PolicyDetail",
    "PolicySummary",
    "PreconditionFailedError",
    "PutObjectResult",
    "RepositoryData",
    "RepositoryWithOrg",
    "Role",
    "SerializationError",
    "ServerError",
    "SourceMetadata",
    "TransportError",
    "ValidationError",
    "ValidationResult",
    # Core
    "__version__",
    "configure",
    "organization",
    "organizations",
    "repository",
]

_default_client: Client | None = None


def configure(
    *,
    api_key: str | None = None,
    endpoint_url: str | None = None,
) -> None:
    """Configure the default client.

    Resets the default client so subsequent calls to :func:`repository` and
    :func:`organizations` use the new configuration.
    """
    global _default_client
    if _default_client is not None:
        _default_client.close()
    _default_client = Client(api_key=api_key, endpoint_url=endpoint_url)


def _get_default_client() -> Client:
    global _default_client
    if _default_client is None:
        _default_client = Client()
    return _default_client


def repository(repo_path: str) -> Repository:
    """Get a repository using the default client.

    Args:
        repo_path: Repository path in ``"org/repo"`` format.
    """
    return _get_default_client().repository(repo_path)


def organization(org: str) -> OrgResource:
    """Get an organization resource using the default client."""
    return _get_default_client().organization(org)


@property  # type: ignore[misc]
def organizations() -> OrganizationCollection:
    """Access organizations using the default client."""
    return _get_default_client().organizations
