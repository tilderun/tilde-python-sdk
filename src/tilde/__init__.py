"""Tilde Python SDK.

Quick start::

    import tilde

    repo = tilde.repository('my-org/repo1')

    with repo.session() as session:
        session.objects.put('foo/bar.csv', b'data')
        session.commit('update data')
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tilde._output_stream import OutputStream
from tilde._version import __version__
from tilde.client import Client
from tilde.exceptions import (
    APIError,
    AuthenticationError,
    BadRequestError,
    CommandError,
    ConfigurationError,
    ConflictError,
    ForbiddenError,
    GoneError,
    LockedError,
    NotFoundError,
    PreconditionFailedError,
    SandboxError,
    SerializationError,
    ServerError,
    TildeError,
    TransportError,
)
from tilde.models import (
    Agent,
    APIKey,
    APIKeyCreated,
    AttachmentRecord,
    CommitData,
    CommitResult,
    ConnectorInfo,
    CopyObjectResult,
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
    RunResult,
    SandboxData,
    SandboxTriggerCondition,
    SandboxTriggerConfig,
    SandboxTriggerData,
    SandboxTriggerRunData,
    SecretEntry,
    SourceMetadata,
    ValidationError,
    ValidationResult,
)

if TYPE_CHECKING:
    from tilde.resources.organizations import OrganizationCollection, OrgResource
    from tilde.resources.repositories import Repository

__all__ = [
    "APIError",
    "APIKey",
    "APIKeyCreated",
    "Agent",
    "AttachmentRecord",
    "AuthenticationError",
    "BadRequestError",
    "Client",
    "CommandError",
    "CommitData",
    "CommitResult",
    "ConfigurationError",
    "ConflictError",
    "ConnectorInfo",
    "CopyObjectResult",
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
    "Organization",
    "OutputStream",
    "Policy",
    "PolicyDetail",
    "PolicySummary",
    "PreconditionFailedError",
    "PutObjectResult",
    "RepositoryData",
    "RepositoryWithOrg",
    "Role",
    "RunResult",
    "SandboxData",
    "SandboxError",
    "SandboxTriggerCondition",
    "SandboxTriggerConfig",
    "SandboxTriggerData",
    "SandboxTriggerRunData",
    "SecretEntry",
    "SerializationError",
    "ServerError",
    "SourceMetadata",
    "TildeError",
    "TransportError",
    "ValidationError",
    "ValidationResult",
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
    default_sandbox_image: str | None = None,
) -> None:
    """Configure the default client.

    Resets the default client so subsequent calls to :func:`repository` and
    :func:`organizations` use the new configuration.
    """
    global _default_client
    if _default_client is not None:
        _default_client.close()
    _default_client = Client(
        api_key=api_key,
        endpoint_url=endpoint_url,
        default_sandbox_image=default_sandbox_image,
    )


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
