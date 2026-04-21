"""Pure value types (leaf module).

Frozen ``@dataclass(slots=True)`` wrappers around individual API payloads.
This module is intentionally a **leaf** in the dependency graph — it imports
only from ``_isoparse`` and the Python standard library.  Every resource
module imports its value types from here directly, which lets
:mod:`tilde.models` eagerly re-export both these value types *and* the entity
classes without a cycle.

User-facing imports should use :mod:`tilde.models`, which re-exports the
same names.
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from typing import TYPE_CHECKING, Any, TypeVar

from tilde._isoparse import parse_iso_datetime

if TYPE_CHECKING:
    from datetime import datetime

    from tilde._output_stream import OutputStream

_T = TypeVar("_T")


def _compact_repr(cls: type[_T]) -> type[_T]:
    """Replace dataclass ``__repr__`` with one that omits default-valued fields."""

    def _repr(self: Any) -> str:
        parts: list[str] = []
        for f in fields(self):
            val = getattr(self, f.name)
            if f.default is not MISSING and val == f.default:
                continue
            if f.default_factory is not MISSING and val == f.default_factory():
                continue
            parts.append(f"{f.name}={val!r}")
        return f"{type(self).__name__}({', '.join(parts)})"

    cls.__repr__ = _repr  # type: ignore[method-assign]
    return cls


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return parse_iso_datetime(value)


# --- Source metadata & object entries -------------------------------------


@_compact_repr
@dataclass(slots=True)
class SourceMetadata:
    connector_id: str = ""
    connector_type: str = ""
    source_path: str = ""
    version_id: str = ""
    source_etag: str = ""
    import_time: datetime | None = None
    import_job_id: str = ""

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
        )


@_compact_repr
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


@_compact_repr
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


@_compact_repr
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


@_compact_repr
@dataclass(slots=True)
class ObjectMetadata:
    """Derived from HEAD response headers."""

    etag: str | None = None
    content_type: str | None = None
    content_length: int | None = None
    reproducible: bool | None = None


@_compact_repr
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


@_compact_repr
@dataclass(slots=True)
class CopyObjectResult:
    source_path: str = ""
    destination_path: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CopyObjectResult:
        return cls(
            source_path=d.get("source_path", ""),
            destination_path=d.get("destination_path", ""),
        )


@_compact_repr
@dataclass(slots=True)
class CommitResult:
    """Structured result from a session commit.

    ``status`` is ``"committed"`` for immediate commits or
    ``"approval_required"`` when a human must approve.
    """

    status: str
    commit_id: str | None = None
    web_url: str | None = None


# --- Policy / group helpers ------------------------------------------------


@_compact_repr
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


@_compact_repr
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


@_compact_repr
@dataclass(slots=True)
class Attachment:
    """A record linking a policy to a principal (user / group / role / agent)."""

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
    def from_dict(cls, d: dict[str, Any]) -> Attachment:
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


@_compact_repr
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


@_compact_repr
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


@_compact_repr
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


# --- Sandbox trigger helpers ----------------------------------------------


@_compact_repr
@dataclass(slots=True)
class SandboxTriggerCondition:
    type: str = ""
    prefix: str = ""
    path: str = ""
    diff_type: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SandboxTriggerCondition:
        return cls(
            type=d.get("type", ""),
            prefix=d.get("prefix", ""),
            path=d.get("path", ""),
            diff_type=d.get("diff_type", ""),
        )


@_compact_repr
@dataclass(slots=True)
class SandboxTriggerConfig:
    image: str
    command: list[str] = field(default_factory=list)
    mountpoint: str = ""
    path_prefix: str = ""
    timeout_seconds: int | None = None
    env_vars: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SandboxTriggerConfig:
        return cls(
            image=d.get("image", ""),
            command=d.get("command", []),
            mountpoint=d.get("mountpoint", ""),
            path_prefix=d.get("path_prefix", ""),
            timeout_seconds=d.get("timeout_seconds"),
            env_vars=d.get("env_vars", {}),
        )


# --- Sandbox command execution ---------------------------------------------


@_compact_repr
@dataclass(slots=True)
class RunResult:
    """Result of a command execution in a sandbox.

    ``stdout`` and ``stderr`` are delivered on independent channels by the
    sandbox ``/exec`` protocol.  Callers that want the merged byte stream
    concatenate explicitly.
    """

    stdout: OutputStream
    stderr: OutputStream
    exit_code: int
