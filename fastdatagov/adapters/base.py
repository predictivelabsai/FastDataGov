from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator


class AdapterError(RuntimeError):
    """Base adapter error safe for worker retry classification."""


class AdapterNotConfigured(AdapterError):
    """Raised when a contract-ready adapter lacks credentials or endpoint config."""


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    metadata: str
    lineage: str
    quality: str
    tags: str
    usage: str
    writeback: str = "none"
    grants: str = "none"


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    key: str
    name: str
    settings: dict[str, Any]
    credential_ref: str = ""


@dataclass(frozen=True, slots=True)
class AssetRecord:
    external_id: str
    qualified_name: str
    name: str
    asset_type: str
    description: str = ""
    source_url: str = ""
    native_metadata: dict[str, Any] = field(default_factory=dict)
    observed_at: datetime | None = None
    deleted: bool = False


@dataclass(frozen=True, slots=True)
class FieldRecord:
    asset_external_id: str
    external_id: str
    name: str
    data_type: str
    ordinal: int
    nullable: bool
    description: str = ""
    native_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LineageRecord:
    source_external_id: str
    target_external_id: str
    operation: str
    evidence_type: str
    confidence: float
    source_field: str = ""
    target_field: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TagRecord:
    asset_external_id: str
    key: str
    value: str
    source: str


@dataclass(frozen=True, slots=True)
class UsageRecord:
    asset_external_id: str
    query_count: int
    distinct_users: int
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True, slots=True)
class GrantRecord:
    asset_external_id: str
    principal_type: str
    principal_key: str
    privilege: str = "discover"
    source: str = "platform_grant"


@dataclass(frozen=True, slots=True)
class QualityRuleSpec:
    asset_external_id: str
    rule_type: str
    expression: str
    threshold: float
    statement_timeout_seconds: int = 120


@dataclass(frozen=True, slots=True)
class QualityResultRecord:
    status: str
    score: float
    observed_value: float
    rows_evaluated: int
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    status: str
    message: str
    latency_ms: int | None = None
    checked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SyncPage:
    records: list[Any]
    next_cursor: dict[str, Any]
    complete: bool = True


class PlatformAdapter(ABC):
    key: str
    display_name: str
    capabilities: AdapterCapabilities

    def __init__(self, connection: ConnectionConfig):
        self.connection = connection

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def health(self) -> AdapterHealth: ...

    @abstractmethod
    def discover_assets(self, cursor: dict[str, Any] | None = None) -> SyncPage: ...

    @abstractmethod
    def discover_fields(self, asset_external_ids: list[str]) -> Iterator[FieldRecord]: ...

    @abstractmethod
    def discover_lineage(self, cursor: dict[str, Any] | None = None) -> SyncPage: ...

    @abstractmethod
    def discover_tags(self, asset_external_ids: list[str]) -> Iterator[TagRecord]: ...

    @abstractmethod
    def discover_usage(self, cursor: dict[str, Any] | None = None) -> SyncPage: ...

    def discover_grants(self, asset_external_ids: list[str]) -> Iterator[GrantRecord]:
        """Yield source-platform discovery grants when the platform exposes them."""
        yield from ()

    @abstractmethod
    def execute_quality(self, rule: QualityRuleSpec) -> QualityResultRecord: ...

    @abstractmethod
    def write_tags(self, asset_external_id: str, tags: dict[str, str]) -> None: ...

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
