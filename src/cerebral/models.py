"""Dataclass models for Cerebral API responses.

All models use ``@dataclass(slots=True)`` with ``from_dict()`` classmethods
that map API JSON to typed Python objects.  Datetime fields are parsed from
ISO 8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


# --- Organizations ---


@dataclass(slots=True)
class Organization:
    id: str
    name: str
    display_name: str
    created_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Organization:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            display_name=d.get("display_name", ""),
            created_at=_parse_dt(d.get("created_at")),
        )


@dataclass(slots=True)
class OrgSummary:
    id: str
    name: str
    display_name: str
    role: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OrgSummary:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            display_name=d.get("display_name", ""),
            role=d.get("role", ""),
        )


@dataclass(slots=True)
class Membership:
    organization_id: str
    user_id: str
    role: str
    joined_at: datetime | None = None
    username: str | None = None
    full_name: str | None = None
    email: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Membership:
        return cls(
            organization_id=d.get("organization_id", ""),
            user_id=d.get("user_id", ""),
            role=d.get("role", ""),
            joined_at=_parse_dt(d.get("joined_at")),
            username=d.get("username"),
            full_name=d.get("full_name"),
            email=d.get("email"),
        )


# --- Repositories ---


@dataclass(slots=True)
class RepositoryData:
    id: str = ""
    organization_id: str = ""
    name: str = ""
    description: str = ""
    visibility: str = ""
    session_max_duration_days: int | None = None
    retention_days: int | None = None
    created_by_type: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RepositoryData:
        return cls(
            id=d.get("id", ""),
            organization_id=d.get("organization_id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            visibility=d.get("visibility", ""),
            session_max_duration_days=d.get("session_max_duration_days"),
            retention_days=d.get("retention_days"),
            created_by_type=d.get("created_by_type", ""),
            created_by=d.get("created_by", ""),
            created_at=_parse_dt(d.get("created_at")),
        )


@dataclass(slots=True)
class RepositoryWithOrg:
    id: str = ""
    name: str = ""
    description: str = ""
    visibility: str = ""
    created_at: datetime | None = None
    organization_slug: str = ""
    organization_display_name: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RepositoryWithOrg:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            visibility=d.get("visibility", ""),
            created_at=_parse_dt(d.get("created_at")),
            organization_slug=d.get("organization_slug", ""),
            organization_display_name=d.get("organization_display_name", ""),
        )


# --- Commits ---


@dataclass(slots=True)
class CommitData:
    id: str = ""
    committer: str = ""
    committer_type: str = ""
    committer_id: str = ""
    message: str = ""
    meta_range_id: str = ""
    creation_date: datetime | None = None
    parents: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    object_count: int | None = None
    total_size: int | None = None
    is_stale: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CommitData:
        return cls(
            id=d.get("id", ""),
            committer=d.get("committer", ""),
            committer_type=d.get("committer_type", ""),
            committer_id=d.get("committer_id", ""),
            message=d.get("message", ""),
            meta_range_id=d.get("meta_range_id", ""),
            creation_date=_parse_dt(d.get("creation_date")),
            parents=d.get("parents", []),
            metadata=d.get("metadata", {}),
            object_count=d.get("object_count"),
            total_size=d.get("total_size"),
            is_stale=d.get("is_stale", False),
        )


# --- Objects ---


@dataclass(slots=True)
class SourceMetadata:
    connector_id: str = ""
    connector_type: str = ""
    source_path: str = ""
    version_id: str = ""
    source_etag: str = ""
    import_time: datetime | None = None
    import_job_id: str = ""
    reproducible: bool | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SourceMetadata:
        return cls(
            connector_id=d.get("connector_id", ""),
            connector_type=d.get("connector_type", ""),
            source_path=d.get("source_path", ""),
            version_id=d.get("version_id", ""),
            source_etag=d.get("source_etag", ""),
            import_time=_parse_dt(d.get("import_time")),
            import_job_id=d.get("import_job_id", ""),
            reproducible=d.get("reproducible"),
        )


@dataclass(slots=True)
class Entry:
    address: str = ""
    last_modified: datetime | None = None
    size: int | None = None
    e_tag: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    address_type: int | None = None
    content_type: str = ""
    source_metadata: SourceMetadata | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Entry:
        sm = d.get("source_metadata")
        return cls(
            address=d.get("address", ""),
            last_modified=_parse_dt(d.get("last_modified")),
            size=d.get("size"),
            e_tag=d.get("e_tag", ""),
            metadata=d.get("metadata", {}),
            address_type=d.get("address_type"),
            content_type=d.get("content_type", ""),
            source_metadata=SourceMetadata.from_dict(sm) if sm else None,
        )


@dataclass(slots=True)
class ListingEntry:
    path: str
    type: str
    entry: Entry | None = None
    status: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ListingEntry:
        entry_d = d.get("entry")
        return cls(
            path=d.get("path", ""),
            type=d.get("type", ""),
            entry=Entry.from_dict(entry_d) if entry_d else None,
            status=d.get("status"),
        )


@dataclass(slots=True)
class EntryRecord:
    path: str = ""
    entry: Entry | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EntryRecord:
        entry_d = d.get("entry")
        return cls(
            path=d.get("path", ""),
            entry=Entry.from_dict(entry_d) if entry_d else None,
        )


@dataclass(slots=True)
class ObjectMetadata:
    """Derived from HEAD response headers."""

    etag: str | None = None
    content_type: str | None = None
    content_length: int | None = None
    reproducible: bool | None = None


@dataclass(slots=True)
class PutObjectResult:
    path: str = ""
    etag: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PutObjectResult:
        return cls(
            path=d.get("path", ""),
            etag=d.get("etag", ""),
        )


@dataclass(slots=True)
class CommitResult:
    """Structured result from a session commit.

    ``status`` is ``"committed"`` for immediate commits or
    ``"approval_required"`` when a human must approve.
    """

    status: str
    commit_id: str | None = None
    web_url: str | None = None


# --- Groups ---


@dataclass(slots=True)
class Group:
    id: str = ""
    organization_id: str = ""
    name: str = ""
    description: str = ""
    created_by_type: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Group:
        return cls(
            id=d.get("id", ""),
            organization_id=d.get("organization_id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            created_by_type=d.get("created_by_type", ""),
            created_by=d.get("created_by", ""),
            created_at=_parse_dt(d.get("created_at")),
        )


@dataclass(slots=True)
class GroupMember:
    subject_type: str = ""
    subject_id: str = ""
    display_name: str = ""
    username: str = ""
    added_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GroupMember:
        return cls(
            subject_type=d.get("subject_type", ""),
            subject_id=d.get("subject_id", ""),
            display_name=d.get("display_name", ""),
            username=d.get("username", ""),
            added_at=_parse_dt(d.get("added_at")),
        )


@dataclass(slots=True)
class GroupDetail:
    """Composite response from ``GET /groups/{group_id}``."""

    group: Group
    members: list[GroupMember] = field(default_factory=list)
    attachments: list[AttachmentRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GroupDetail:
        return cls(
            group=Group.from_dict(d.get("group", {})),
            members=[GroupMember.from_dict(m) for m in d.get("members", [])],
            attachments=[AttachmentRecord.from_dict(a) for a in d.get("attachments", [])],
        )


@dataclass(slots=True)
class EffectiveGroup:
    group_id: str = ""
    group_name: str = ""
    description: str = ""
    source: str = ""
    source_name: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EffectiveGroup:
        return cls(
            group_id=d.get("group_id", ""),
            group_name=d.get("group_name", ""),
            description=d.get("description", ""),
            source=d.get("source", ""),
            source_name=d.get("source_name", ""),
        )


# --- Policies ---


@dataclass(slots=True)
class Policy:
    id: str = ""
    organization_id: str = ""
    name: str = ""
    description: str = ""
    rego: str = ""
    is_builtin: bool = False
    created_by_type: str = ""
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Policy:
        return cls(
            id=d.get("id", ""),
            organization_id=d.get("organization_id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            rego=d.get("rego", ""),
            is_builtin=d.get("is_builtin", False),
            created_by_type=d.get("created_by_type", ""),
            created_by=d.get("created_by", ""),
            created_at=_parse_dt(d.get("created_at")),
            updated_at=_parse_dt(d.get("updated_at")),
        )


@dataclass(slots=True)
class PolicySummary:
    id: str = ""
    organization_id: str = ""
    name: str = ""
    description: str = ""
    is_builtin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    attachment_count: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PolicySummary:
        return cls(
            id=d.get("id", ""),
            organization_id=d.get("organization_id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            is_builtin=d.get("is_builtin", False),
            created_at=_parse_dt(d.get("created_at")),
            updated_at=_parse_dt(d.get("updated_at")),
            attachment_count=d.get("attachment_count", 0),
        )


@dataclass(slots=True)
class AttachmentRecord:
    policy_id: str = ""
    policy_name: str = ""
    is_builtin: bool = False
    principal_type: str = ""
    principal_id: str = ""
    principal_name: str = ""
    attached_by_type: str = ""
    attached_by: str = ""
    attached_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AttachmentRecord:
        return cls(
            policy_id=d.get("policy_id", ""),
            policy_name=d.get("policy_name", ""),
            is_builtin=d.get("is_builtin", False),
            principal_type=d.get("principal_type", ""),
            principal_id=d.get("principal_id", ""),
            principal_name=d.get("principal_name", ""),
            attached_by_type=d.get("attached_by_type", ""),
            attached_by=d.get("attached_by", ""),
            attached_at=_parse_dt(d.get("attached_at")),
        )


@dataclass(slots=True)
class PolicyDetail:
    """Composite response from ``GET /policies/{policy_id}``."""

    policy: Policy
    attachments: list[AttachmentRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PolicyDetail:
        return cls(
            policy=Policy.from_dict(d.get("policy", {})),
            attachments=[AttachmentRecord.from_dict(a) for a in d.get("attachments", [])],
        )


@dataclass(slots=True)
class EffectivePolicy:
    policy_id: str = ""
    policy_name: str = ""
    is_builtin: bool = False
    source: str = ""
    source_name: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EffectivePolicy:
        return cls(
            policy_id=d.get("policy_id", ""),
            policy_name=d.get("policy_name", ""),
            is_builtin=d.get("is_builtin", False),
            source=d.get("source", ""),
            source_name=d.get("source_name", ""),
        )


@dataclass(slots=True)
class ValidationError:
    line: int = 0
    column: int = 0
    message: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ValidationError:
        return cls(
            line=d.get("line", 0),
            column=d.get("column", 0),
            message=d.get("message", ""),
        )


@dataclass(slots=True)
class ValidationResult:
    valid: bool = False
    errors: list[ValidationError] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ValidationResult:
        return cls(
            valid=d.get("valid", False),
            errors=[ValidationError.from_dict(e) for e in d.get("errors", [])],
        )


# --- Connectors ---


@dataclass(slots=True)
class ConnectorInfo:
    id: str = ""
    name: str = ""
    type: str = ""
    disabled: bool = False
    created_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ConnectorInfo:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            type=d.get("type", ""),
            disabled=d.get("disabled", False),
            created_at=_parse_dt(d.get("created_at")),
        )


# --- Import ---


@dataclass(slots=True)
class ImportJob:
    id: str = ""
    repository_id: str = ""
    connector_id: str = ""
    source_path: str = ""
    destination_path: str = ""
    use_versioning: bool = False
    commit_message: str = ""
    status: str = ""
    objects_imported: int | None = None
    commit_id: str = ""
    error: str = ""
    created_by_type: str = ""
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ImportJob:
        return cls(
            id=d.get("id", ""),
            repository_id=d.get("repository_id", ""),
            connector_id=d.get("connector_id", ""),
            source_path=d.get("source_path", ""),
            destination_path=d.get("destination_path", ""),
            use_versioning=d.get("use_versioning", False),
            commit_message=d.get("commit_message", ""),
            status=d.get("status", ""),
            objects_imported=d.get("objects_imported"),
            commit_id=d.get("commit_id", ""),
            error=d.get("error", ""),
            created_by_type=d.get("created_by_type", ""),
            created_by=d.get("created_by", ""),
            created_at=_parse_dt(d.get("created_at")),
            updated_at=_parse_dt(d.get("updated_at")),
        )


# --- Roles ---


@dataclass(slots=True)
class Role:
    id: str = ""
    organization_id: str = ""
    name: str = ""
    description: str = ""
    created_by_type: str = ""
    created_by: str = ""
    created_by_name: str = ""
    created_at: datetime | None = None
    last_used_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Role:
        return cls(
            id=d.get("id", ""),
            organization_id=d.get("organization_id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            created_by_type=d.get("created_by_type", ""),
            created_by=d.get("created_by", ""),
            created_by_name=d.get("created_by_name", ""),
            created_at=_parse_dt(d.get("created_at")),
            last_used_at=_parse_dt(d.get("last_used_at")),
        )


# --- Agents ---


@dataclass(slots=True)
class Agent:
    id: str = ""
    organization_id: str = ""
    name: str = ""
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    created_by_type: str = ""
    created_at: datetime | None = None
    last_used_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Agent:
        return cls(
            id=d.get("id", ""),
            organization_id=d.get("organization_id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            metadata=d.get("metadata", {}),
            created_by_type=d.get("created_by_type", ""),
            created_at=_parse_dt(d.get("created_at")),
            last_used_at=_parse_dt(d.get("last_used_at")),
        )


@dataclass(slots=True)
class APIKey:
    id: str = ""
    name: str = ""
    description: str = ""
    token_hint: str = ""
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> APIKey:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            token_hint=d.get("token_hint", ""),
            created_at=_parse_dt(d.get("created_at")),
            last_used_at=_parse_dt(d.get("last_used_at")),
            revoked_at=_parse_dt(d.get("revoked_at")),
        )


@dataclass(slots=True)
class APIKeyCreated:
    id: str = ""
    name: str = ""
    description: str = ""
    token: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> APIKeyCreated:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            token=d.get("token", ""),
        )
