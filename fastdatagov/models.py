from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AssetField:
    name: str
    data_type: str
    description: str = ""
    classification: str = ""
    nullable: bool = True
    business_description: str = ""


@dataclass(slots=True)
class Asset:
    id: int
    name: str
    qualified_name: str
    asset_type: str
    platform: str
    domain: str
    description: str
    business_description: str
    owner: str
    steward: str
    sensitivity: str
    certification: str
    quality_score: float
    trust_score: float
    freshness: str
    access_guidance: str
    tags: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    fields: list[AssetField] = field(default_factory=list)
    usage_30d: int = 0
    source_url: str = ""
    certified_at: str = ""
    certification_expires: str = ""
    owner_attested_at: str = ""
    native_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LineageEdge:
    id: int
    source_id: int
    target_id: int
    operation: str
    evidence_type: str
    confidence: float
    source_field: str = ""
    target_field: str = ""


@dataclass(slots=True)
class QualityRule:
    id: int
    asset_id: int
    name: str
    rule_type: str
    status: str
    score: float
    severity: str
    schedule: str
    last_run: str
    expression: str
    trend: list[float] = field(default_factory=list)
    enabled: bool = True


@dataclass(slots=True)
class WorkItem:
    id: int
    kind: str
    asset_id: int
    title: str
    status: str
    priority: str
    assignee: str
    due: str
    description: str = ""


@dataclass(slots=True)
class GlossaryTerm:
    id: int
    name: str
    definition: str
    domain: str
    owner: str
    status: str
    linked_assets: int


@dataclass(slots=True)
class AdapterStatus:
    key: str
    name: str
    status: str
    last_sync: str
    assets: int
    health: str
    capabilities: dict[str, str]
    message: str = ""


@dataclass(slots=True)
class AuditEvent:
    id: int
    actor: str
    action: str
    entity: str
    occurred_at: str
    detail: str


@dataclass(slots=True)
class UserIdentity:
    subject: str
    email: str
    name: str
    roles: tuple[str, ...] = ("consumer",)
    groups: tuple[str, ...] = ()

    @property
    def is_governance_admin(self) -> bool:
        return bool({"admin", "governance_lead"}.intersection(self.roles))

    def can(self, *roles: str) -> bool:
        return self.is_governance_admin or bool(set(roles).intersection(self.roles))


@dataclass(slots=True)
class DataProduct:
    id: int
    key: str
    name: str
    description: str
    domain: str
    owner: str
    steward: str
    status: str
    service_level: str
    access_guidance: str
    certification: str
    asset_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class Domain:
    id: int
    key: str
    name: str
    description: str = ""
    parent_id: int | None = None


@dataclass(slots=True)
class AccountabilityAssignment:
    id: int
    scope_type: str
    scope_id: int
    responsibility: str
    assignee_email: str
    attested_at: str = ""
    expires_at: str = ""


@dataclass(slots=True)
class WorkComment:
    id: int
    work_item_id: int
    author_email: str
    body: str
    created_at: str


@dataclass(slots=True)
class JobStatus:
    id: int
    kind: str
    status: str
    attempts: int
    run_after: str
    last_error: str = ""


@dataclass(slots=True)
class PilotMetric:
    key: str
    label: str
    unit: str
    baseline: float | None
    target: float | None
    current_value: float | None
    measured_at: str = ""
    notes: str = ""


JsonDict = dict[str, Any]
