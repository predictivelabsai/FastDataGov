from __future__ import annotations

from dataclasses import asdict, replace
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from typing import Protocol

from psycopg.types.json import Jsonb

from fastdatagov.adapters.registry import adapter_registry
from fastdatagov.config import settings
from fastdatagov.db import connect, execute, fetch_all, fetch_one
from fastdatagov.models import (
    AdapterStatus,
    Asset,
    AssetField,
    AuditEvent,
    AccountabilityAssignment,
    DataProduct,
    Domain,
    GlossaryTerm,
    JobStatus,
    LineageEdge,
    PilotMetric,
    QualityRule,
    UserIdentity,
    WorkComment,
    WorkItem,
)
from fastdatagov.synthetic.data import ADAPTERS, ASSETS, AUDIT, GLOSSARY, LINEAGE, QUALITY_RULES, WORK_ITEMS


def _queue_notifications(cursor, event_type: str, recipient: str, subject: str, body: str, payload: dict | None = None) -> None:
    cursor.execute(
        """INSERT INTO fastdatagov.notification_outbox (channel_id,event_type,recipient,subject,body,payload)
           SELECT id,%s,%s,%s,%s,%s FROM fastdatagov.notification_channels
           WHERE enabled AND (cardinality(events)=0 OR %s=ANY(events))""",
        (event_type,recipient or None,subject,body,Jsonb(payload or {}),event_type),
    )


def _recompute_trust(cursor, asset_id: int) -> None:
    cursor.execute("""UPDATE fastdatagov.assets SET trust_score=least(100,
        coalesce(quality_score,0)*0.55 + CASE certification_status WHEN 'certified' THEN 15 WHEN 'verified' THEN 10 ELSE 0 END +
        CASE WHEN owner_email IS NOT NULL AND owner_email<>'' THEN 10 ELSE 0 END +
        CASE WHEN steward_email IS NOT NULL AND steward_email<>'' THEN 10 ELSE 0 END +
        CASE WHEN business_description<>'' THEN 5 ELSE 0 END +
        CASE WHEN coalesce(refreshed_at,last_observed_at)>=now()-interval '7 days' THEN 5 ELSE 0 END),updated_at=now() WHERE id=%s""",(asset_id,))


def _contains_secret(value) -> bool:
    secret_keys={"password","private_key","token","client_secret","secret","access_key"}
    if isinstance(value,dict): return any(str(key).lower() in secret_keys or _contains_secret(item) for key,item in value.items())
    if isinstance(value,list): return any(_contains_secret(item) for item in value)
    return False


class GovernanceRepository(Protocol):
    def metrics(self, identity: UserIdentity | None = None) -> dict: ...
    def list_assets(self, query: str = "", platform: str = "", domain: str = "", trust: str = "", identity: UserIdentity | None = None, owner: str = "", sensitivity: str = "", refreshed: str = "", limit: int = 0, offset: int = 0, asset_id: int = 0) -> list[Asset]: ...
    def catalog_facets(self, identity: UserIdentity | None = None) -> dict[str,list[str]]: ...
    def get_asset(self, asset_id: int, identity: UserIdentity | None = None) -> Asset | None: ...
    def lineage(self, asset_id: int | None = None, identity: UserIdentity | None = None) -> list[LineageEdge]: ...
    def quality_rules(self, identity: UserIdentity | None = None) -> list[QualityRule]: ...
    def work_items(self, kind: str = "", status: str = "", identity: UserIdentity | None = None) -> list[WorkItem]: ...
    def update_work_item(self, item_id: int, status: str, actor: UserIdentity) -> WorkItem | None: ...
    def create_work_item(self, kind: str, asset_id: int, actor: UserIdentity) -> WorkItem: ...
    def glossary(self, query: str = "", identity: UserIdentity | None = None) -> list[GlossaryTerm]: ...
    def adapters(self, identity: UserIdentity | None = None) -> list[AdapterStatus]: ...
    def audit(self, limit: int = 20, identity: UserIdentity | None = None) -> list[AuditEvent]: ...
    def domains(self) -> list[Domain]: ...
    def save_domain(self, actor: UserIdentity, name: str, description: str = "", parent_id: int | None = None, domain_id: int | None = None) -> Domain: ...
    def products(self, identity: UserIdentity | None = None) -> list[DataProduct]: ...
    def save_product(self, actor: UserIdentity, name: str, description: str, domain: str, owner: str, steward: str, status: str, service_level: str, access_guidance: str, asset_ids: list[int], product_id: int | None = None) -> DataProduct: ...
    def update_asset_metadata(self, asset_id: int, actor: UserIdentity, business_description: str, owner: str, steward: str, sensitivity: str, access_guidance: str, tags: list[str], term_ids: list[int]) -> Asset: ...
    def update_field_metadata(self, asset_id: int, field_name: str, actor: UserIdentity, business_description: str, classification: str) -> AssetField: ...
    def save_term(self, actor: UserIdentity, name: str, definition: str, domain: str, owner: str, status: str, term_id: int | None = None) -> GlossaryTerm: ...
    def save_lineage(self, actor: UserIdentity, source_id: int, target_id: int, operation: str, confidence: float, evidence_type: str = "manual") -> LineageEdge: ...
    def delete_lineage(self, edge_id: int, actor: UserIdentity) -> None: ...
    def save_quality_rule(self, actor: UserIdentity, asset_id: int, name: str, rule_type: str, expression: str, threshold: float, severity: str, schedule: str, rule_id: int | None = None) -> QualityRule: ...
    def queue_quality_run(self, rule_id: int, actor: UserIdentity) -> int: ...
    def set_quality_enabled(self, rule_id: int, actor: UserIdentity, enabled: bool) -> None: ...
    def work_comments(self, item_id: int) -> list[WorkComment]: ...
    def add_work_comment(self, item_id: int, actor: UserIdentity, body: str) -> WorkComment: ...
    def certify_asset(self, asset_id: int, actor: UserIdentity, status: str, expires_days: int, notes: str = "") -> None: ...
    def certify_product(self, product_id: int, actor: UserIdentity, status: str, expires_days: int, notes: str = "") -> None: ...
    def assignments(self, scope_type: str = "", scope_id: int = 0) -> list[AccountabilityAssignment]: ...
    def assign_accountability(self, actor: UserIdentity, scope_type: str, scope_id: int, responsibility: str, email: str, expires_days: int = 365) -> AccountabilityAssignment: ...
    def roles(self) -> list[dict]: ...
    def save_role(self, actor: UserIdentity, principal_type: str, principal_key: str, role: str, scope_type: str = "global", scope_key: str = "") -> dict: ...
    def delete_role(self, actor: UserIdentity, role_id: int) -> None: ...
    def jobs(self, limit: int = 50) -> list[JobStatus]: ...
    def pilot_metrics(self) -> list[PilotMetric]: ...
    def workflow_definitions(self) -> list[dict]: ...
    def save_workflow_definition(self, actor: UserIdentity, kind: str, due_days: int, approval_role: str, enabled: bool) -> dict: ...
    def notification_channels(self) -> list[dict]: ...
    def save_notification_channel(self, actor: UserIdentity, key: str, channel_type: str, endpoint_ref: str, events: list[str], enabled: bool = True) -> dict: ...
    def connection_details(self) -> list[dict]: ...
    def save_connection(self, actor: UserIdentity, key: str, name: str, adapter_type: str, credential_ref: str, config: dict) -> dict: ...
    def queue_adapter_job(self, actor: UserIdentity, key: str, kind: str) -> int: ...
    def principal_aliases(self) -> list[dict]: ...
    def save_principal_alias(self, actor: UserIdentity, identity_principal_type: str, identity_key: str, platform_key: str, source_principal_key: str) -> dict: ...
    def delete_principal_alias(self, actor: UserIdentity, alias_id: int) -> None: ...
    def queue_tag_writeback(self, actor: UserIdentity, asset_id: int, tags: dict[str, str]) -> int: ...


class DemoRepository:
    """Mutable deterministic repository used for evaluation and local development."""

    def __init__(self) -> None:
        self._assets = deepcopy(ASSETS)
        self._work = deepcopy(WORK_ITEMS)
        self._audit = deepcopy(AUDIT)
        self._lineage = deepcopy(LINEAGE)
        self._quality = deepcopy(QUALITY_RULES)
        self._glossary = deepcopy(GLOSSARY)
        self._comments: list[WorkComment] = []
        self._domains = [Domain(index, name.lower().replace(" ", "-"), name) for index, name in enumerate(sorted({a.domain for a in ASSETS} | {t.domain for t in GLOSSARY}), 1)]
        self._products = [
            DataProduct(1, "customer-360", "Customer 360", "Reusable customer insight product with quality and lineage evidence.", "Customer", "alex.owner@example.com", "sam.steward@example.com", "active", "Daily by 08:00 UTC; 99.5% availability", "Request CUSTOMER_ANALYTICS access.", "verified", [7, 10]),
            DataProduct(2, "revenue-reporting", "Revenue reporting", "Certified finance reporting assets and semantic model.", "Finance", "noah.owner@example.com", "ivy.steward@example.com", "active", "Hourly refresh", "Available to approved finance users.", "certified", [4, 11]),
        ]
        self._assignments: list[AccountabilityAssignment] = []
        self._roles: list[dict] = [{"id": 1, "principal_type": "group", "principal_key": "data-governance", "role": "governance_lead", "scope_type": "global", "scope_key": ""}]
        self._jobs = [JobStatus(1, "adapter.sync", "succeeded", 1, "12 minutes ago"), JobStatus(2, "quality.run", "succeeded", 1, "24 minutes ago")]
        self._workflows = [{"kind":kind,"display_name":kind.title(),"due_days":days,"approval_role":"owner","enabled":True} for kind,days in (("quality",3),("certification",7),("metadata",7),("access",3),("attestation",14))]
        self._channels: list[dict] = []
        self._connections = [{"key":a.key,"name":a.name,"adapter_type":a.key,"credential_ref":"","config":{},"status":a.status} for a in ADAPTERS]
        self._aliases: list[dict] = []

    def reset(self) -> None:
        self.__init__()

    def metrics(self, identity: UserIdentity | None = None) -> dict:
        assets = self.list_assets(identity=identity)
        quality = [r.score for r in self._quality]
        certified = sum(1 for asset in assets if asset.certification == "certified")
        assigned = sum(1 for asset in assets if asset.owner and asset.steward)
        return {
            "assets": len(assets),
            "platforms": len({asset.platform for asset in assets}),
            "catalog_coverage": 96,
            "quality_score": round(sum(quality) / len(quality), 1),
            "certified_pct": round(certified / len(assets) * 100),
            "accountability_pct": round(assigned / len(assets) * 100),
            "open_work": sum(1 for item in self._work if item.status not in {"approved", "resolved", "rejected"}),
            "domains": len({asset.domain for asset in assets}),
        }

    def list_assets(self, query: str = "", platform: str = "", domain: str = "", trust: str = "", identity: UserIdentity | None = None, owner: str = "", sensitivity: str = "", refreshed: str = "", limit: int = 0, offset: int = 0, asset_id: int = 0) -> list[Asset]:
        query = query.strip().lower()
        result = self._assets
        if query:
            result = [
                asset for asset in result
                if query in " ".join([
                    asset.name, asset.qualified_name, asset.description,
                    asset.business_description, " ".join(asset.tags), " ".join(asset.terms), asset.owner, asset.steward,
                    " ".join(f"{f.name} {f.description} {f.classification}" for f in asset.fields),
                ]).lower()
            ]
        if platform:
            result = [asset for asset in result if asset.platform.lower() == platform.lower()]
        if domain:
            result = [asset for asset in result if asset.domain.lower() == domain.lower()]
        if trust == "certified":
            result = [asset for asset in result if asset.certification == "certified"]
        elif trust == "attention":
            result = [asset for asset in result if asset.quality_score < 90]
        if owner: result=[asset for asset in result if owner.lower() in asset.owner.lower()]
        if sensitivity: result=[asset for asset in result if asset.sensitivity==sensitivity]
        if asset_id: result=[asset for asset in result if asset.id==asset_id]
        result=sorted(result, key=lambda asset: (-asset.trust_score, asset.name))
        return result[offset:offset+limit] if limit else result[offset:]

    def get_asset(self, asset_id: int, identity: UserIdentity | None = None) -> Asset | None:
        return next((asset for asset in self._assets if asset.id == asset_id), None)

    def catalog_facets(self,identity=None):
        assets=self.list_assets(identity=identity)
        return {"platforms":sorted({a.platform for a in assets}),"domains":sorted({a.domain for a in assets}),"owners":sorted({a.owner for a in assets if a.owner}),"sensitivities":sorted({a.sensitivity for a in assets})}

    def lineage(self, asset_id: int | None = None, identity: UserIdentity | None = None) -> list[LineageEdge]:
        if asset_id is None:
            return list(self._lineage)
        return [edge for edge in self._lineage if edge.source_id == asset_id or edge.target_id == asset_id]

    def quality_rules(self, identity: UserIdentity | None = None) -> list[QualityRule]:
        return list(self._quality)

    def work_items(self, kind: str = "", status: str = "", identity: UserIdentity | None = None) -> list[WorkItem]:
        result = self._work
        if identity is not None and not identity.is_governance_admin and not identity.can("steward","owner","engineer"):
            result=[item for item in result if item.assignee==identity.email or identity.email in item.description]
        if kind:
            result = [item for item in result if item.kind == kind]
        if status:
            result = [item for item in result if item.status == status]
        return list(result)

    def update_work_item(self, item_id: int, status: str, actor: UserIdentity) -> WorkItem | None:
        allowed = {"open", "in_progress", "waiting", "approved", "resolved", "rejected"}
        if status not in allowed:
            raise ValueError(f"Unsupported work item status: {status}")
        for index, item in enumerate(self._work):
            if item.id != item_id:
                continue
            transitions={"open":{"in_progress","rejected"},"in_progress":{"resolved","waiting","rejected"},"waiting":{"in_progress","approved","rejected"},"approved":{"open"},"resolved":{"open"},"rejected":{"open"}}
            if status not in transitions.get(item.status,set()): raise ValueError(f"Unsupported workflow transition: {item.status} to {status}")
            if status=="approved":
                definition=next(w for w in self._workflows if w["kind"]==item.kind)
                if not actor.can(definition["approval_role"]): raise PermissionError("Approval role is required")
            updated = replace(item, status=status)
            self._work[index] = updated
            self._audit.insert(0, AuditEvent(
                max(event.id for event in self._audit) + 1,
                actor.email,
                f"marked {item.kind} work {status.replace('_', ' ')}",
                item.title,
                "Just now",
                f"Workflow status changed from {item.status} to {status}.",
            ))
            return updated
        return None

    def create_work_item(self, kind: str, asset_id: int, actor: UserIdentity) -> WorkItem:
        allowed = {"quality", "certification", "metadata", "access", "attestation"}
        if kind not in allowed:
            raise ValueError(f"Unsupported work item kind: {kind}")
        asset = self.get_asset(asset_id)
        if not asset:
            raise ValueError("Asset does not exist")
        titles = {
            "quality": f"Review quality for {asset.name}",
            "certification": f"Certify {asset.name}",
            "metadata": f"Enrich metadata for {asset.name}",
            "access": f"Access request for {asset.name}",
            "attestation": f"Attest ownership of {asset.name}",
        }
        definition=next((w for w in self._workflows if w["kind"]==kind and w["enabled"]),None)
        if not definition: raise ValueError("Workflow is disabled")
        assignee = asset.owner if kind in {"access", "attestation", "certification"} else asset.steward
        assignee=assignee or settings().governance_fallback_assignee
        item = WorkItem(max((work.id for work in self._work), default=0) + 1, kind, asset.id, titles[kind], "open", "medium", assignee, f"In {definition['due_days']} days", f"Requested by {actor.email} from the asset workspace.")
        self._work.append(item)
        self._audit.insert(0, AuditEvent(max(event.id for event in self._audit) + 1, actor.email, f"created {kind} work", asset.name, "Just now", item.title))
        return item

    def glossary(self, query: str = "", identity: UserIdentity | None = None) -> list[GlossaryTerm]:
        query = query.strip().lower()
        if not query:
            return list(self._glossary)
        return [term for term in self._glossary if query in f"{term.name} {term.definition} {term.domain}".lower()]

    def adapters(self, identity: UserIdentity | None = None) -> list[AdapterStatus]:
        return list(ADAPTERS)

    def audit(self, limit: int = 20, identity: UserIdentity | None = None) -> list[AuditEvent]:
        return self._audit[:limit]

    def _record(self, actor: UserIdentity, action: str, entity: str, detail: str = "") -> None:
        self._audit.insert(0, AuditEvent(max((e.id for e in self._audit), default=0) + 1, actor.email, action, entity, "Just now", detail))

    def domains(self) -> list[Domain]:
        return list(self._domains)

    def save_domain(self, actor, name, description="", parent_id=None, domain_id=None):
        if not name.strip(): raise ValueError("Domain name is required")
        if parent_id and not any(d.id==parent_id for d in self._domains): raise ValueError("Parent domain does not exist")
        if domain_id and parent_id:
            current=parent_id
            while current:
                if current==domain_id: raise ValueError("Domain hierarchy cannot contain a cycle")
                current=next((d.parent_id for d in self._domains if d.id==current),None)
        if domain_id:
            old = next((d for d in self._domains if d.id == domain_id), None)
            if not old: raise ValueError("Domain does not exist")
            item = Domain(old.id, old.key, name.strip(), description.strip(), parent_id)
            self._domains[self._domains.index(old)] = item
        else:
            item = Domain(max((d.id for d in self._domains), default=0) + 1, name.lower().strip().replace(" ", "-"), name.strip(), description.strip(), parent_id)
            self._domains.append(item)
        self._record(actor, "saved domain", item.name)
        return item

    def products(self, identity=None):
        visible = {a.id for a in self.list_assets(identity=identity)}
        return [replace(p, asset_ids=[i for i in p.asset_ids if i in visible]) for p in self._products if not p.asset_ids or any(i in visible for i in p.asset_ids)]

    def save_product(self, actor, name, description, domain, owner, steward, status, service_level, access_guidance, asset_ids, product_id=None):
        if status not in {"draft", "active", "deprecated"}: raise ValueError("Unsupported product status")
        if not name.strip(): raise ValueError("Product name is required")
        if "@" not in owner or "@" not in steward: raise ValueError("Owner and steward emails are required")
        key = name.lower().strip().replace(" ", "-")
        if product_id:
            old = next((p for p in self._products if p.id == product_id), None)
            if not old: raise ValueError("Product does not exist")
            item = DataProduct(old.id, old.key, name.strip(), description.strip(), domain, owner, steward, status, service_level, access_guidance, old.certification, asset_ids)
            self._products[self._products.index(old)] = item
        else:
            item = DataProduct(max((p.id for p in self._products), default=0)+1, key, name.strip(), description.strip(), domain, owner, steward, status, service_level, access_guidance, "uncertified", asset_ids)
            self._products.append(item)
        self._record(actor, "saved data product", item.name)
        return item

    def update_asset_metadata(self, asset_id, actor, business_description, owner, steward, sensitivity, access_guidance, tags, term_ids):
        asset = self.get_asset(asset_id, actor)
        if not asset: raise ValueError("Asset does not exist or is not visible")
        if sensitivity not in {"public", "internal", "confidential", "restricted"}: raise ValueError("Unsupported sensitivity")
        if "@" not in owner or "@" not in steward: raise ValueError("Owner and steward emails are required")
        terms = [t.name for t in self._glossary if t.id in term_ids]
        updated = replace(asset, business_description=business_description.strip(), owner=owner.strip(), steward=steward.strip(), sensitivity=sensitivity, access_guidance=access_guidance.strip(), tags=sorted(set(tags)), terms=terms)
        self._assets[self._assets.index(asset)] = updated
        self._record(actor, "updated asset metadata", asset.name)
        return updated

    def update_field_metadata(self, asset_id, field_name, actor, business_description, classification):
        asset=self.get_asset(asset_id,actor)
        if not asset: raise ValueError("Asset does not exist")
        field=next((f for f in asset.fields if f.name==field_name),None)
        if not field: raise ValueError("Field does not exist")
        updated=replace(field,business_description=business_description.strip(),classification=classification.strip())
        asset.fields[asset.fields.index(field)]=updated; self._record(actor,"updated field metadata",f"{asset.name}.{field_name}"); return updated

    def save_term(self, actor, name, definition, domain, owner, status, term_id=None):
        if status not in {"draft", "in_review", "approved", "deprecated"}: raise ValueError("Unsupported term status")
        if not name.strip() or not definition.strip(): raise ValueError("Name and definition are required")
        if "@" not in owner: raise ValueError("Owner email is required")
        if term_id:
            old = next((t for t in self._glossary if t.id == term_id), None)
            if not old: raise ValueError("Term does not exist")
            item = GlossaryTerm(old.id, name.strip(), definition.strip(), domain, owner.strip(), status, old.linked_assets)
            self._glossary[self._glossary.index(old)] = item
        else:
            item = GlossaryTerm(max((t.id for t in self._glossary), default=0)+1, name.strip(), definition.strip(), domain, owner.strip(), status, 0)
            self._glossary.append(item)
        self._record(actor, "saved glossary term", item.name)
        return item

    def save_lineage(self, actor, source_id, target_id, operation, confidence, evidence_type="manual"):
        if source_id == target_id: raise ValueError("Lineage endpoints must differ")
        if not self.get_asset(source_id, actor) or not self.get_asset(target_id, actor): raise ValueError("Lineage endpoint is not visible")
        if evidence_type not in {"manual","inferred","native","query_history"}: raise ValueError("Unsupported lineage evidence")
        edge = LineageEdge(max((e.id for e in self._lineage), default=0)+1, source_id, target_id, operation.strip() or "transforms", evidence_type, max(0, min(1, confidence)))
        self._lineage.append(edge); self._record(actor, "created manual lineage", str(edge.id)); return edge

    def delete_lineage(self, edge_id, actor):
        edge = next((e for e in self._lineage if e.id == edge_id and e.evidence_type == "manual"), None)
        if not edge: raise ValueError("Only manual lineage can be removed")
        self._lineage.remove(edge); self._record(actor, "removed manual lineage", str(edge_id))

    def save_quality_rule(self, actor, asset_id, name, rule_type, expression, threshold, severity, schedule, rule_id=None):
        if rule_type not in {"completeness", "uniqueness", "validity", "consistency", "freshness", "custom_sql", "custom_python"}: raise ValueError("Unsupported rule type")
        if severity not in {"low", "medium", "high", "critical"}: raise ValueError("Unsupported severity")
        if schedule not in {"hourly","daily","weekly","manual"} or not 0<=threshold<=100: raise ValueError("Unsupported schedule or threshold")
        if not self.get_asset(asset_id, actor) or not name.strip() or not expression.strip(): raise ValueError("Asset, name and expression are required")
        if rule_id:
            old = next((r for r in self._quality if r.id == rule_id), None)
            if not old: raise ValueError("Rule does not exist")
            item = QualityRule(old.id, asset_id, name.strip(), rule_type, old.status, old.score, severity, schedule, old.last_run, expression.strip(), old.trend,old.enabled)
            self._quality[self._quality.index(old)] = item
        else:
            item = QualityRule(max((r.id for r in self._quality), default=0)+1, asset_id, name.strip(), rule_type, "queued", 0, severity, schedule, "Never", expression.strip(), [])
            self._quality.append(item)
        self._record(actor, "saved quality rule", item.name, f"Threshold {threshold}"); return item

    def queue_quality_run(self, rule_id, actor):
        if not any(r.id == rule_id for r in self._quality): raise ValueError("Rule does not exist")
        existing=next((j for j in self._jobs if j.kind=="quality.run" and j.status in {"queued","running"}),None)
        if existing: return existing.id
        job = JobStatus(max((j.id for j in self._jobs), default=0)+1, "quality.run", "queued", 0, "Now")
        self._jobs.insert(0, job); self._record(actor, "queued quality run", str(rule_id)); return job.id

    def set_quality_enabled(self,rule_id,actor,enabled):
        rule=next((r for r in self._quality if r.id==rule_id),None)
        if not rule: raise ValueError("Rule does not exist")
        self._quality[self._quality.index(rule)]=replace(rule,enabled=enabled); self._record(actor,"enabled quality rule" if enabled else "disabled quality rule",rule.name)

    def work_comments(self, item_id): return [c for c in self._comments if c.work_item_id == item_id]

    def add_work_comment(self, item_id, actor, body):
        if not body.strip(): raise ValueError("Comment is required")
        if not any(w.id == item_id for w in self._work): raise ValueError("Work item does not exist")
        item = WorkComment(max((c.id for c in self._comments), default=0)+1, item_id, actor.email, body.strip(), "Just now")
        self._comments.append(item); self._record(actor, "commented on work", str(item_id)); return item

    def certify_asset(self, asset_id, actor, status, expires_days, notes=""):
        if status not in {"certified", "verified", "rejected", "expired"}: raise ValueError("Unsupported certification status")
        asset = self.get_asset(asset_id, actor)
        if not asset: raise ValueError("Asset does not exist")
        self._assets[self._assets.index(asset)] = replace(asset, certification=status)
        self._record(actor, "certified asset", asset.name, notes or f"Expires in {expires_days} days")

    def certify_product(self, product_id, actor, status, expires_days, notes=""):
        if status not in {"certified","verified","rejected","expired"}: raise ValueError("Unsupported certification status")
        product=next((p for p in self._products if p.id==product_id),None)
        if not product: raise ValueError("Product does not exist")
        self._products[self._products.index(product)]=replace(product,certification=status); self._record(actor,"certified data product",product.name,notes or f"Expires in {expires_days} days")

    def assignments(self, scope_type="", scope_id=0):
        return [a for a in self._assignments if (not scope_type or a.scope_type == scope_type) and (not scope_id or a.scope_id == scope_id)]

    def assign_accountability(self, actor, scope_type, scope_id, responsibility, email, expires_days=365):
        if scope_type not in {"domain", "product", "asset"} or responsibility not in {"owner", "steward"}: raise ValueError("Invalid accountability assignment")
        exists=(scope_type=="asset" and self.get_asset(scope_id,actor)) or (scope_type=="product" and any(p.id==scope_id for p in self.products(actor))) or (scope_type=="domain" and any(d.id==scope_id for d in self.domains()))
        if not exists or "@" not in email: raise ValueError("Accountability scope does not exist or email is invalid")
        item = AccountabilityAssignment(max((a.id for a in self._assignments), default=0)+1, scope_type, scope_id, responsibility, email.strip(), "Just now", f"In {expires_days} days")
        self._assignments.append(item); self._record(actor, "assigned accountability", f"{scope_type}:{scope_id}", email); return item

    def roles(self): return list(self._roles)

    def save_role(self, actor, principal_type, principal_key, role, scope_type="global", scope_key=""):
        allowed = {"consumer", "steward", "owner", "engineer", "governance_lead", "admin"}
        if principal_type not in {"user", "group"} or role not in allowed or scope_type!="global": raise ValueError("Only global application role bindings are supported; use accountability assignments for domain/asset responsibility")
        item = {"id": max((r["id"] for r in self._roles), default=0)+1, "principal_type": principal_type, "principal_key": principal_key, "role": role, "scope_type": scope_type, "scope_key": scope_key}
        self._roles.append(item); self._record(actor, "created role binding", principal_key, role); return item

    def delete_role(self,actor,role_id):
        row=next((r for r in self._roles if r["id"]==role_id),None)
        if not row: raise ValueError("Role binding does not exist")
        self._roles.remove(row); self._record(actor,"removed role binding",str(role_id))

    def jobs(self, limit=50): return self._jobs[:limit]

    def pilot_metrics(self):
        metrics = self.metrics()
        return [PilotMetric("catalog_coverage", "Catalog coverage", "percent", 60, 90, metrics["catalog_coverage"], "Now"), PilotMetric("accountability_coverage", "Owner and steward coverage", "percent", 45, 90, metrics["accountability_pct"], "Now"), PilotMetric("quality_rule_coverage", "Quality rule coverage", "percent", 20, 75, 75, "Now"), PilotMetric("time_to_trusted_data", "Time to trusted data", "hours", 32, 8, 12, "Now"), PilotMetric("weekly_active_users", "Weekly active users", "users", 0, 20, 14, "Now")]

    def workflow_definitions(self): return list(self._workflows)

    def save_workflow_definition(self, actor, kind, due_days, approval_role, enabled):
        row=next((w for w in self._workflows if w["kind"]==kind),None)
        if not row or due_days < 1: raise ValueError("Invalid workflow definition")
        row.update(due_days=due_days,approval_role=approval_role,enabled=enabled); self._record(actor,"updated workflow",kind); return dict(row)

    def notification_channels(self): return list(self._channels)

    def save_notification_channel(self, actor, key, channel_type, endpoint_ref, events, enabled=True):
        if channel_type not in {"email","teams","slack","webhook"} or not key.strip() or not endpoint_ref.startswith("env:"): raise ValueError("Notification channels require a key, supported type and env: secret reference")
        row=next((c for c in self._channels if c["key"]==key),None) or {"id":len(self._channels)+1,"key":key}
        row.update(channel_type=channel_type,endpoint_ref=endpoint_ref,events=events,enabled=enabled)
        if row not in self._channels:self._channels.append(row)
        self._record(actor,"saved notification channel",key); return dict(row)

    def connection_details(self): return list(self._connections)

    def save_connection(self, actor, key, name, adapter_type, credential_ref, config):
        if adapter_type not in {"snowflake","fabric","databricks","demo"} or (credential_ref and not credential_ref.startswith("env:")): raise ValueError("Invalid adapter or credential reference")
        if _contains_secret(config): raise ValueError("Connection configuration cannot contain secret values")
        row=next((c for c in self._connections if c["key"]==key),None) or {"key":key,"status":"not_configured"}
        row.update(name=name,adapter_type=adapter_type,credential_ref=credential_ref,config=config)
        if row not in self._connections:self._connections.append(row)
        self._record(actor,"saved connection",key); return dict(row)

    def queue_adapter_job(self, actor, key, kind):
        if kind not in {"adapter.sync","adapter.health"} or not any(c["key"]==key for c in self._connections): raise ValueError("Invalid adapter job")
        existing=next((j for j in self._jobs if j.kind==kind and j.status in {"queued","running"}),None)
        if existing:return existing.id
        job=JobStatus(max((j.id for j in self._jobs),default=0)+1,kind,"queued",0,"Now"); self._jobs.insert(0,job); self._record(actor,"queued adapter job",key,kind); return job.id

    def principal_aliases(self): return list(self._aliases)

    def save_principal_alias(self, actor, identity_principal_type, identity_key, platform_key, source_principal_key):
        if identity_principal_type not in {"user","group"} or not all(v.strip() for v in (identity_key,platform_key,source_principal_key)): raise ValueError("Invalid principal alias")
        row={"id":len(self._aliases)+1,"identity_principal_type":identity_principal_type,"identity_key":identity_key.strip(),"platform_key":platform_key.strip(),"source_principal_key":source_principal_key.strip()}; self._aliases.append(row); self._record(actor,"created principal alias",identity_key,source_principal_key); return row

    def delete_principal_alias(self,actor,alias_id):
        row=next((a for a in self._aliases if a["id"]==alias_id),None)
        if not row: raise ValueError("Principal alias does not exist")
        self._aliases.remove(row); self._record(actor,"removed principal alias",str(alias_id))

    def queue_tag_writeback(self, actor, asset_id, tags):
        if not self.get_asset(asset_id,actor): raise ValueError("Asset does not exist")
        if not tags: raise ValueError("At least one native tag is required")
        job=JobStatus(max((j.id for j in self._jobs),default=0)+1,"adapter.tags","queued",0,"Now"); self._jobs.insert(0,job); self._record(actor,"queued native tag writeback",str(asset_id),", ".join(tags)); return job.id


class PostgresRepository:
    """Persistent repository with source-grant-aware discovery."""

    @staticmethod
    def _visibility(identity: UserIdentity | None, alias: str = "a") -> tuple[str, tuple]:
        if identity is None or identity.is_governance_admin:
            return "", ()
        principals = [identity.email, *identity.groups]
        return (
            f" AND (NOT EXISTS (SELECT 1 FROM fastdatagov.asset_visibility av0 WHERE av0.asset_id={alias}.id) "
            f"OR EXISTS (SELECT 1 FROM fastdatagov.asset_visibility av WHERE av.asset_id={alias}.id "
            f"AND (av.principal_type='public' OR av.principal_key = ANY(%s) OR EXISTS (SELECT 1 FROM fastdatagov.principal_aliases pa WHERE pa.platform_key={alias}.platform_key AND pa.source_principal_key=av.principal_key AND ((pa.identity_principal_type='user' AND pa.identity_key=%s) OR (pa.identity_principal_type='group' AND pa.identity_key=ANY(%s)))))))",
            (principals,identity.email,list(identity.groups)),
        )

    def metrics(self, identity: UserIdentity | None = None) -> dict:
        assets = self.list_assets(identity=identity)
        rules = self.quality_rules(identity=identity)
        return {
            "assets": len(assets),
            "platforms": len({a.platform for a in assets}),
            "catalog_coverage": 100 if assets else 0,
            "quality_score": round(sum(r.score for r in rules) / len(rules), 1) if rules else 0,
            "certified_pct": round(sum(a.certification == "certified" for a in assets) / len(assets) * 100) if assets else 0,
            "accountability_pct": round(sum(bool(a.owner and a.steward) for a in assets) / len(assets) * 100) if assets else 0,
            "open_work": sum(item.status not in {"approved","resolved","rejected"} for item in self.work_items(identity=identity)),
            "domains": len({a.domain for a in assets}),
        }

    def list_assets(self, query: str = "", platform: str = "", domain: str = "", trust: str = "", identity: UserIdentity | None = None, owner: str = "", sensitivity: str = "", refreshed: str = "", limit: int = 0, offset: int = 0, asset_id: int = 0) -> list[Asset]:
        conditions = ["a.deleted_at IS NULL"]
        params: list = []
        if query:
            conditions.append("(to_tsvector('english', coalesce(a.name,'') || ' ' || coalesce(a.qualified_name,'') || ' ' || coalesce(a.description,'') || ' ' || coalesce(a.business_description,'')) @@ plainto_tsquery('english', %s) OR EXISTS (SELECT 1 FROM fastdatagov.asset_tags sat JOIN fastdatagov.tags st ON st.id=sat.tag_id WHERE sat.asset_id=a.id AND to_tsvector('english',coalesce(st.label,'')||' '||coalesce(st.key,''))@@plainto_tsquery('english',%s)) OR EXISTS (SELECT 1 FROM fastdatagov.asset_terms satm JOIN fastdatagov.glossary_terms sgt ON sgt.id=satm.term_id WHERE satm.asset_id=a.id AND to_tsvector('english',coalesce(sgt.name,'')||' '||coalesce(sgt.definition,''))@@plainto_tsquery('english',%s)) OR EXISTS (SELECT 1 FROM fastdatagov.asset_fields saf WHERE saf.asset_id=a.id AND to_tsvector('english',coalesce(saf.name,'')||' '||coalesce(saf.description,'')||' '||coalesce(saf.business_description,'')||' '||coalesce(saf.classification,''))@@plainto_tsquery('english',%s)))")
            params.extend((query,query,query,query))
        if platform:
            conditions.append("lower(a.platform_key)=lower(%s)")
            params.append(platform)
        if domain:
            conditions.append("lower(d.name)=lower(%s)")
            params.append(domain)
        if trust == "certified":
            conditions.append("a.certification_status='certified'")
        elif trust == "attention":
            conditions.append("a.quality_score < 90")
        if owner: conditions.append("a.owner_email ILIKE %s"); params.append(f"%{owner}%")
        if sensitivity: conditions.append("a.sensitivity=%s"); params.append(sensitivity)
        if asset_id: conditions.append("a.id=%s"); params.append(asset_id)
        windows={"24h":"1 day","7d":"7 days","30d":"30 days"}
        if refreshed in windows: conditions.append("coalesce(a.refreshed_at,a.last_observed_at)>=now()-(%s)::interval"); params.append(windows[refreshed])
        visibility_sql, visibility_params = self._visibility(identity)
        params.extend(visibility_params)
        paging=""
        if limit: paging=" LIMIT %s OFFSET %s"; params.extend((limit,max(0,offset)))
        rows = fetch_all(
            """
            SELECT a.*, d.name AS domain_name,
                   coalesce(array_agg(DISTINCT CASE WHEN atag.tag_value<>'' THEN t.label||': '||atag.tag_value ELSE t.label END) FILTER (WHERE t.id IS NOT NULL), '{}') AS tags,
                   coalesce(array_agg(DISTINCT gt.name) FILTER (WHERE gt.id IS NOT NULL), '{}') AS terms,
                   coalesce((SELECT sum(u.query_count) FROM fastdatagov.usage_rollups u
                             WHERE u.asset_id=a.id AND u.usage_date >= current_date - 30), 0) AS usage_30d,
                   coalesce((SELECT certified_at::text FROM fastdatagov.certifications c WHERE c.asset_id=a.id ORDER BY certified_at DESC LIMIT 1),'') certified_at,
                   coalesce((SELECT expires_at::text FROM fastdatagov.certifications c WHERE c.asset_id=a.id ORDER BY certified_at DESC LIMIT 1),'') certification_expires,
                   coalesce((SELECT attested_at::text FROM fastdatagov.accountability_assignments aa WHERE aa.scope_type='asset' AND aa.scope_id=a.id AND aa.responsibility='owner' ORDER BY attested_at DESC NULLS LAST LIMIT 1),'') owner_attested_at
            FROM fastdatagov.assets a
            LEFT JOIN fastdatagov.domains d ON d.id=a.domain_id
            LEFT JOIN fastdatagov.asset_tags atag ON atag.asset_id=a.id
            LEFT JOIN fastdatagov.tags t ON t.id=atag.tag_id
            LEFT JOIN fastdatagov.asset_terms aterm ON aterm.asset_id=a.id
            LEFT JOIN fastdatagov.glossary_terms gt ON gt.id=aterm.term_id
            WHERE """ + " AND ".join(conditions) + visibility_sql + """
            GROUP BY a.id, d.name
            ORDER BY a.trust_score DESC NULLS LAST, a.name
            """ + paging,
            tuple(params),
        )
        return [self._asset_from_row(row) for row in rows]

    def get_asset(self, asset_id: int, identity: UserIdentity | None = None) -> Asset | None:
        assets = self.list_assets(identity=identity,asset_id=asset_id,limit=1)
        if not assets:
            return None
        asset = assets[0]
        field_rows = fetch_all(
            "SELECT name, data_type, description, classification, nullable, business_description FROM fastdatagov.asset_fields WHERE asset_id=%s ORDER BY ordinal NULLS LAST, id",
            (asset_id,),
        )
        asset.fields = [AssetField(**row) for row in field_rows]
        return asset

    def catalog_facets(self,identity=None):
        visibility_sql,visibility_params=self._visibility(identity,"a")
        row=fetch_one("SELECT coalesce(array_agg(DISTINCT initcap(a.platform_key)) FILTER (WHERE a.platform_key IS NOT NULL),'{}') platforms,coalesce(array_agg(DISTINCT d.name) FILTER (WHERE d.name IS NOT NULL),'{}') domains,coalesce(array_agg(DISTINCT a.owner_email) FILTER (WHERE a.owner_email IS NOT NULL AND a.owner_email<>''),'{}') owners,coalesce(array_agg(DISTINCT a.sensitivity) FILTER (WHERE a.sensitivity IS NOT NULL),'{}') sensitivities FROM fastdatagov.assets a LEFT JOIN fastdatagov.domains d ON d.id=a.domain_id WHERE a.deleted_at IS NULL"+visibility_sql,visibility_params)
        return {key:sorted(row[key]) for key in ("platforms","domains","owners","sensitivities")}

    @staticmethod
    def _asset_from_row(row: dict) -> Asset:
        return Asset(
            id=row["id"], name=row["name"], qualified_name=row["qualified_name"],
            asset_type=row["asset_type"], platform=row["platform_key"].title(),
            domain=row.get("domain_name") or "Unassigned", description=row.get("description") or "",
            business_description=row.get("business_description") or "", owner=row.get("owner_email") or "",
            steward=row.get("steward_email") or "", sensitivity=row.get("sensitivity") or "internal",
            certification=row.get("certification_status") or "uncertified",
            quality_score=float(row.get("quality_score") or 0), trust_score=float(row.get("trust_score") or 0),
            freshness=str(row.get("refreshed_at") or row.get("last_observed_at") or ""),
            access_guidance=row.get("access_guidance") or "", tags=list(row.get("tags") or []),
            terms=list(row.get("terms") or []), usage_30d=int(row.get("usage_30d") or 0),
            source_url=row.get("source_url") or "",
            certified_at=row.get("certified_at") or "",certification_expires=row.get("certification_expires") or "",owner_attested_at=row.get("owner_attested_at") or "",
            native_metadata=dict(row.get("native_metadata") or {}),
        )

    def lineage(self, asset_id: int | None = None, identity: UserIdentity | None = None) -> list[LineageEdge]:
        conditions = ["true"]
        params: list = []
        if asset_id is not None:
            conditions.append("(le.source_asset_id=%s OR le.target_asset_id=%s)")
            params.extend((asset_id, asset_id))
        source_visibility, source_params = self._visibility(identity, "source_asset")
        target_visibility, target_params = self._visibility(identity, "target_asset")
        params.extend(source_params)
        params.extend(target_params)
        rows = fetch_all(
            "SELECT le.id, le.source_asset_id, le.target_asset_id, le.operation, le.evidence_type, le.confidence, coalesce(sf.name,'') source_field, coalesce(tf.name,'') target_field "
            "FROM fastdatagov.lineage_edges le "
            "JOIN fastdatagov.assets source_asset ON source_asset.id=le.source_asset_id "
            "JOIN fastdatagov.assets target_asset ON target_asset.id=le.target_asset_id "
            "LEFT JOIN fastdatagov.asset_fields sf ON sf.id=le.source_field_id "
            "LEFT JOIN fastdatagov.asset_fields tf ON tf.id=le.target_field_id "
            "WHERE " + " AND ".join(conditions) + source_visibility + target_visibility + " ORDER BY le.id",
            tuple(params),
        )
        return [LineageEdge(row["id"], row["source_asset_id"], row["target_asset_id"], row["operation"], row["evidence_type"], float(row["confidence"]),row["source_field"],row["target_field"]) for row in rows]

    def quality_rules(self, identity: UserIdentity | None = None) -> list[QualityRule]:
        visibility_sql, visibility_params = self._visibility(identity)
        rows = fetch_all(
            """
            SELECT qr.*, coalesce(qrun.status, 'queued') AS run_status,
                   coalesce(qrun.score, 0) AS score, coalesce(qrun.completed_at, qrun.started_at) AS last_run,
                   coalesce((SELECT array_agg(recent.score ORDER BY recent.started_at) FROM
                       (SELECT score,started_at FROM fastdatagov.quality_runs history WHERE history.rule_id=qr.id AND score IS NOT NULL ORDER BY started_at DESC LIMIT 7) recent), '{}') trend
            FROM fastdatagov.quality_rules qr
            JOIN fastdatagov.assets a ON a.id=qr.asset_id
            LEFT JOIN LATERAL (SELECT * FROM fastdatagov.quality_runs r WHERE r.rule_id=qr.id ORDER BY r.started_at DESC LIMIT 1) qrun ON true
            WHERE a.deleted_at IS NULL
            """ + visibility_sql + " ORDER BY qr.severity, qr.name",
            visibility_params,
        )
        return [QualityRule(row["id"], row["asset_id"], row["name"], row["rule_type"], row["run_status"], float(row["score"]), row["severity"], row["schedule"], str(row["last_run"]), row["expression"], [float(v) for v in row["trend"]],row["enabled"]) for row in rows]

    def work_items(self, kind: str = "", status: str = "", identity: UserIdentity | None = None) -> list[WorkItem]:
        conditions, params = ["true"], []
        if kind:
            conditions.append("kind=%s"); params.append(kind)
        if status:
            conditions.append("status=%s"); params.append(status)
        if identity is not None and not identity.is_governance_admin and not identity.can("steward","owner","engineer"):
            conditions.append("(w.assignee_email=%s OR w.requester_email=%s)"); params.extend((identity.email,identity.email))
        visibility_sql, visibility_params = self._visibility(identity)
        params.extend(visibility_params)
        rows = fetch_all("SELECT w.* FROM fastdatagov.work_items w LEFT JOIN fastdatagov.assets a ON a.id=w.asset_id WHERE " + " AND ".join(conditions) + " AND (w.asset_id IS NULL OR (true" + visibility_sql + ")) ORDER BY CASE w.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, w.due_at NULLS LAST", tuple(params))
        return [WorkItem(row["id"], row["kind"], row.get("asset_id") or 0, row["title"], row["status"], row["priority"], row.get("assignee_email") or "", str(row.get("due_at") or "No due date"), row.get("description") or "") for row in rows]

    def update_work_item(self, item_id: int, status: str, actor: UserIdentity) -> WorkItem | None:
        if status not in {"open", "in_progress", "waiting", "approved", "resolved", "rejected"}:
            raise ValueError("Unsupported work item status")
        visible=next((item for item in self.work_items(identity=actor) if item.id==item_id),None)
        if not visible: return None
        transitions={"open":{"in_progress","rejected"},"in_progress":{"resolved","waiting","rejected"},"waiting":{"in_progress","approved","rejected"},"approved":{"open"},"resolved":{"open"},"rejected":{"open"}}
        if status not in transitions.get(visible.status,set()): raise ValueError(f"Unsupported workflow transition: {visible.status} to {status}")
        if status=="approved":
            definition=next((w for w in self.workflow_definitions() if w["kind"]==visible.kind),None)
            if definition and not actor.can(definition["approval_role"]): raise PermissionError("Approval role is required")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fastdatagov.work_items SET status=%s, updated_at=now() WHERE id=%s", (status, item_id))
            cursor.execute("INSERT INTO fastdatagov.work_item_events (work_item_id,actor_email,event_type,from_status,to_status) VALUES (%s,%s,'status_changed',%s,%s)",(item_id,actor.email,visible.status,status))
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject, action, entity_type, entity_key, before_data, after_data) VALUES (%s, 'workflow.status_changed', 'work_item', %s, jsonb_build_object('status', %s::text), jsonb_build_object('status', %s::text))", (actor.subject, str(item_id), visible.status, status))
            _queue_notifications(cursor,"workflow.status_changed",visible.assignee,f"Governance work {status.replace('_',' ')}",visible.title,{"work_item_id":item_id,"status":status})
            connection.commit()
        return next((item for item in self.work_items(identity=actor) if item.id == item_id), None)

    def create_work_item(self, kind: str, asset_id: int, actor: UserIdentity) -> WorkItem:
        if kind not in {"quality", "certification", "metadata", "access", "attestation"}:
            raise ValueError("Unsupported work item kind")
        asset = self.get_asset(asset_id, actor)
        if not asset:
            raise ValueError("Asset does not exist or is not visible")
        titles = {
            "quality": f"Review quality for {asset.name}",
            "certification": f"Certify {asset.name}",
            "metadata": f"Enrich metadata for {asset.name}",
            "access": f"Access request for {asset.name}",
            "attestation": f"Attest ownership of {asset.name}",
        }
        assignee = asset.owner if kind in {"access", "attestation", "certification"} else asset.steward
        assignee=assignee or settings().governance_fallback_assignee
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT due_days FROM fastdatagov.workflow_definitions WHERE kind=%s AND enabled",(kind,)); definition=cursor.fetchone()
            if not definition: raise ValueError("Workflow is disabled")
            cursor.execute("INSERT INTO fastdatagov.work_items (kind,asset_id,title,description,requester_email,assignee_email,due_at) VALUES (%s,%s,%s,%s,%s,%s,now()+(%s||' days')::interval) RETURNING id", (kind, asset_id, titles[kind], f"Requested by {actor.email} from the asset workspace.", actor.email, assignee,definition[0]))
            item_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.work_item_events (work_item_id,actor_email,event_type,to_status) VALUES (%s,%s,'created','open')",(item_id,actor.email))
            _queue_notifications(cursor,"workflow.created",assignee,"New governance work",titles[kind],{"work_item_id":item_id,"kind":kind,"asset_id":asset_id})
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'workflow.created','asset',%s,jsonb_build_object('kind',%s::text))", (actor.subject, str(asset_id), kind))
            connection.commit()
        return next(item for item in self.work_items(identity=actor) if item.id == item_id)

    def glossary(self, query: str = "", identity: UserIdentity | None = None) -> list[GlossaryTerm]:
        query_params: list = []
        where = ""
        if query:
            where = "WHERE to_tsvector('english',coalesce(gt.name,'')||' '||coalesce(gt.definition,''))@@plainto_tsquery('english',%s)"
            query_params.append(query)
        visibility_sql,visibility_params=self._visibility(identity,"linked_asset")
        rows = fetch_all(f"SELECT gt.id, gt.name, gt.definition, coalesce(d.name, 'Unassigned') domain, coalesce(gt.owner_email, '') owner, gt.status, (SELECT count(*) FROM fastdatagov.asset_terms linked JOIN fastdatagov.assets linked_asset ON linked_asset.id=linked.asset_id WHERE linked.term_id=gt.id AND linked_asset.deleted_at IS NULL{visibility_sql}) linked_assets FROM fastdatagov.glossary_terms gt LEFT JOIN fastdatagov.domains d ON d.id=gt.domain_id {where} ORDER BY gt.name", tuple(visibility_params)+tuple(query_params))
        return [GlossaryTerm(**row) for row in rows]

    def adapters(self, identity: UserIdentity | None = None) -> list[AdapterStatus]:
        rows = fetch_all("SELECT c.key, c.name, c.status, coalesce(c.last_sync_at::text, 'Never') last_sync, count(a.id) assets, CASE WHEN c.last_error IS NULL THEN 'Healthy' ELSE 'Attention' END health, p.adapter_type, coalesce(c.last_error, '') message FROM fastdatagov.connections c JOIN fastdatagov.platforms p ON p.id=c.platform_id LEFT JOIN fastdatagov.assets a ON a.connection_id=c.id AND a.deleted_at IS NULL GROUP BY c.id,p.adapter_type ORDER BY c.name")
        result=[]
        for row in rows:
            adapter_type=row.pop("adapter_type"); capabilities=adapter_registry.get(adapter_type)
            manifest=asdict(capabilities.capabilities) if capabilities else {}
            result.append(AdapterStatus(**row,capabilities=manifest))
        if identity is not None and not identity.is_governance_admin:
            visibility_sql,visibility_params=self._visibility(identity,"a")
            exact=[]
            for item in result:
                count=fetch_one("SELECT count(*) count FROM fastdatagov.assets a JOIN fastdatagov.connections c ON c.id=a.connection_id WHERE c.key=%s AND a.deleted_at IS NULL"+visibility_sql,(item.key,*visibility_params))["count"]
                exact.append(replace(item,assets=count))
            result=exact
        return result

    def audit(self, limit: int = 20, identity: UserIdentity | None = None) -> list[AuditEvent]:
        where=""; params:list=[]
        if identity is not None and not identity.is_governance_admin:
            where="WHERE actor_subject IN (%s,%s)"; params.extend((identity.subject,identity.email))
        params.append(limit)
        rows = fetch_all(f"SELECT id, actor_subject actor, replace(action, '_', ' ') action, entity_key entity, created_at::text occurred_at, coalesce(after_data::text, '') detail FROM fastdatagov.audit_events {where} ORDER BY created_at DESC LIMIT %s", tuple(params))
        return [AuditEvent(**row) for row in rows]

    def domains(self) -> list[Domain]:
        return [Domain(**row) for row in fetch_all("SELECT id,key,name,description,parent_id FROM fastdatagov.domains ORDER BY name")]

    def save_domain(self, actor, name, description="", parent_id=None, domain_id=None):
        name = name.strip()
        if not name: raise ValueError("Domain name is required")
        if parent_id and domain_id and parent_id == domain_id: raise ValueError("A domain cannot be its own parent")
        if parent_id and not any(d.id==parent_id for d in self.domains()): raise ValueError("Parent domain does not exist")
        if domain_id and parent_id:
            cycle=fetch_one("WITH RECURSIVE descendants AS (SELECT id FROM fastdatagov.domains WHERE id=%s UNION ALL SELECT d.id FROM fastdatagov.domains d JOIN descendants x ON d.parent_id=x.id) SELECT 1 found FROM descendants WHERE id=%s",(domain_id,parent_id))
            if cycle: raise ValueError("Domain hierarchy cannot contain a cycle")
        key = "-".join(name.lower().split())
        with connect() as connection, connection.cursor() as cursor:
            if domain_id:
                cursor.execute("UPDATE fastdatagov.domains SET name=%s,description=%s,parent_id=%s WHERE id=%s RETURNING id", (name, description.strip(), parent_id, domain_id))
            else:
                cursor.execute("INSERT INTO fastdatagov.domains (key,name,description,parent_id) VALUES (%s,%s,%s,%s) RETURNING id", (key, name, description.strip(), parent_id))
            row = cursor.fetchone()
            if not row: raise ValueError("Domain does not exist")
            saved_id = row[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'domain.saved','domain',%s,jsonb_build_object('name',%s::text))", (actor.subject, str(saved_id), name))
            connection.commit()
        return next(d for d in self.domains() if d.id == saved_id)

    def products(self, identity=None):
        visible = {asset.id for asset in self.list_assets(identity=identity)}
        rows = fetch_all("""
            SELECT p.*, coalesce(d.name,'Unassigned') domain,
                   coalesce(array_agg(pa.asset_id) FILTER (WHERE pa.asset_id IS NOT NULL), '{}') asset_ids,
                   count(pa.asset_id) linked_count
            FROM fastdatagov.data_products p
            LEFT JOIN fastdatagov.domains d ON d.id=p.domain_id
            LEFT JOIN fastdatagov.product_assets pa ON pa.product_id=p.id
            GROUP BY p.id,d.name ORDER BY p.name
        """)
        products = [(DataProduct(row["id"], row["key"], row["name"], row["description"], row["domain"], row.get("owner_email") or "", row.get("steward_email") or "", row["status"], row["service_level"], row["access_guidance"], row["certification_status"], [i for i in row["asset_ids"] if i in visible]),row["linked_count"]) for row in rows]
        return [product for product,linked_count in products if linked_count==0 or product.asset_ids]

    def save_product(self, actor, name, description, domain, owner, steward, status, service_level, access_guidance, asset_ids, product_id=None):
        if status not in {"draft", "active", "deprecated"}: raise ValueError("Unsupported product status")
        if not name.strip(): raise ValueError("Product name is required")
        if "@" not in owner or "@" not in steward: raise ValueError("Owner and steward emails are required")
        domain_row = next((d for d in self.domains() if d.name == domain), None)
        if not domain_row: raise ValueError("Domain does not exist")
        visible = {a.id for a in self.list_assets(identity=actor)}
        if not set(asset_ids).issubset(visible): raise ValueError("A selected asset is not visible")
        key = "-".join(name.lower().split())
        with connect() as connection, connection.cursor() as cursor:
            if product_id:
                cursor.execute("UPDATE fastdatagov.data_products SET name=%s,description=%s,domain_id=%s,owner_email=%s,steward_email=%s,status=%s,service_level=%s,access_guidance=%s,updated_at=now() WHERE id=%s RETURNING id", (name.strip(),description.strip(),domain_row.id,owner.strip(),steward.strip(),status,service_level.strip(),access_guidance.strip(),product_id))
            else:
                cursor.execute("INSERT INTO fastdatagov.data_products (key,name,description,domain_id,owner_email,steward_email,status,service_level,access_guidance) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id", (key,name.strip(),description.strip(),domain_row.id,owner.strip(),steward.strip(),status,service_level.strip(),access_guidance.strip()))
            row = cursor.fetchone()
            if not row: raise ValueError("Product does not exist")
            saved_id = row[0]
            cursor.execute("DELETE FROM fastdatagov.product_assets WHERE product_id=%s", (saved_id,))
            cursor.executemany("INSERT INTO fastdatagov.product_assets (product_id,asset_id) VALUES (%s,%s)", [(saved_id, aid) for aid in sorted(set(asset_ids))])
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'product.saved','data_product',%s,jsonb_build_object('name',%s::text))", (actor.subject,str(saved_id),name.strip()))
            connection.commit()
        return next(p for p in self.products(actor) if p.id == saved_id)

    def update_asset_metadata(self, asset_id, actor, business_description, owner, steward, sensitivity, access_guidance, tags, term_ids):
        asset = self.get_asset(asset_id, actor)
        if not asset: raise ValueError("Asset does not exist or is not visible")
        if sensitivity not in {"public", "internal", "confidential", "restricted"}: raise ValueError("Unsupported sensitivity")
        if "@" not in owner or "@" not in steward: raise ValueError("Owner and steward emails are required")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT coalesce(max(version),0)+1 FROM fastdatagov.asset_revisions WHERE asset_id=%s", (asset_id,)); version=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.asset_revisions (asset_id,version,snapshot,change_note,changed_by) VALUES (%s,%s,%s,'Business metadata update',%s)", (asset_id,version,Jsonb(asdict(asset)),actor.email))
            cursor.execute("UPDATE fastdatagov.assets SET business_description=%s,owner_email=%s,steward_email=%s,sensitivity=%s,access_guidance=%s,updated_at=now() WHERE id=%s", (business_description.strip(),owner.strip(),steward.strip(),sensitivity,access_guidance.strip(),asset_id))
            _recompute_trust(cursor,asset_id)
            cursor.execute("DELETE FROM fastdatagov.asset_tags WHERE asset_id=%s AND source='fastdatagov'", (asset_id,))
            for label in sorted({t.strip() for t in tags if t.strip()}):
                key = "-".join(label.lower().split())
                cursor.execute("INSERT INTO fastdatagov.tags (key,label) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET label=excluded.label RETURNING id", (key,label)); tag_id=cursor.fetchone()[0]
                cursor.execute("INSERT INTO fastdatagov.asset_tags (asset_id,tag_id,source) VALUES (%s,%s,'fastdatagov') ON CONFLICT (asset_id,tag_id) DO UPDATE SET source='fastdatagov'", (asset_id,tag_id))
            cursor.execute("DELETE FROM fastdatagov.asset_terms WHERE asset_id=%s", (asset_id,))
            cursor.executemany("INSERT INTO fastdatagov.asset_terms (asset_id,term_id) VALUES (%s,%s)", [(asset_id, tid) for tid in sorted(set(term_ids))])
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,before_data,after_data) VALUES (%s,'asset.metadata_updated','asset',%s,%s,jsonb_build_object('version',%s::integer))", (actor.subject,str(asset_id),Jsonb(asdict(asset)),version))
            connection.commit()
        return self.get_asset(asset_id, actor)

    def update_field_metadata(self, asset_id, field_name, actor, business_description, classification):
        if not self.get_asset(asset_id,actor): raise ValueError("Asset does not exist or is not visible")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fastdatagov.asset_fields SET business_description=%s,classification=%s,business_updated_by=%s,business_updated_at=now() WHERE asset_id=%s AND name=%s RETURNING id",(business_description.strip(),classification.strip(),actor.email,asset_id,field_name)); row=cursor.fetchone()
            if not row: raise ValueError("Field does not exist")
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'field.metadata_updated','asset_field',%s,jsonb_build_object('classification',%s::text))",(actor.subject,str(row[0]),classification.strip())); connection.commit()
        return next(field for field in self.get_asset(asset_id,actor).fields if field.name==field_name)

    def save_term(self, actor, name, definition, domain, owner, status, term_id=None):
        if status not in {"draft", "in_review", "approved", "deprecated"}: raise ValueError("Unsupported term status")
        if not name.strip() or not definition.strip(): raise ValueError("Name and definition are required")
        if "@" not in owner: raise ValueError("Owner email is required")
        domain_row = next((d for d in self.domains() if d.name == domain), None)
        if not domain_row: raise ValueError("Domain does not exist")
        key = "-".join(name.lower().split())
        with connect() as connection, connection.cursor() as cursor:
            if term_id:
                cursor.execute("INSERT INTO fastdatagov.glossary_term_revisions (term_id,version,snapshot,change_note,changed_by) SELECT id,version,to_jsonb(gt),'Term update',%s FROM fastdatagov.glossary_terms gt WHERE id=%s", (actor.email,term_id))
                cursor.execute("UPDATE fastdatagov.glossary_terms SET name=%s,definition=%s,domain_id=%s,owner_email=%s,status=%s,version=version+1,updated_at=now() WHERE id=%s RETURNING id", (name.strip(),definition.strip(),domain_row.id,owner.strip(),status,term_id))
            else:
                cursor.execute("INSERT INTO fastdatagov.glossary_terms (key,name,definition,domain_id,owner_email,status) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id", (key,name.strip(),definition.strip(),domain_row.id,owner.strip(),status))
            row=cursor.fetchone()
            if not row: raise ValueError("Term does not exist")
            saved_id=row[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'glossary.saved','glossary_term',%s,jsonb_build_object('name',%s::text))", (actor.subject,str(saved_id),name.strip()))
            connection.commit()
        return next(t for t in self.glossary() if t.id == saved_id)

    def save_lineage(self, actor, source_id, target_id, operation, confidence, evidence_type="manual"):
        if source_id == target_id: raise ValueError("Lineage endpoints must differ")
        if not self.get_asset(source_id, actor) or not self.get_asset(target_id, actor): raise ValueError("Lineage endpoint is not visible")
        if evidence_type not in {"manual","inferred","native","query_history"}: raise ValueError("Unsupported lineage evidence")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO fastdatagov.lineage_edges (source_asset_id,target_asset_id,operation,evidence_type,confidence,created_by) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (source_asset_id,target_asset_id,source_field_id,target_field_id,operation) DO UPDATE SET evidence_type=excluded.evidence_type,confidence=excluded.confidence,observed_at=now() RETURNING id", (source_id,target_id,operation.strip() or "transforms",evidence_type,max(0,min(1,confidence)),actor.email)); edge_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'lineage.created','lineage_edge',%s,jsonb_build_object('source',%s::bigint,'target',%s::bigint))", (actor.subject,str(edge_id),source_id,target_id)); connection.commit()
        return next(e for e in self.lineage(identity=actor) if e.id == edge_id)

    def delete_lineage(self, edge_id, actor):
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM fastdatagov.lineage_edges WHERE id=%s AND evidence_type='manual' RETURNING id", (edge_id,))
            if not cursor.fetchone(): raise ValueError("Only manual lineage can be removed")
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'lineage.removed','lineage_edge',%s)", (actor.subject,str(edge_id))); connection.commit()

    def save_quality_rule(self, actor, asset_id, name, rule_type, expression, threshold, severity, schedule, rule_id=None):
        if rule_type not in {"completeness", "uniqueness", "validity", "consistency", "freshness", "custom_sql", "custom_python"}: raise ValueError("Unsupported rule type")
        if severity not in {"low", "medium", "high", "critical"}: raise ValueError("Unsupported severity")
        if schedule not in {"hourly","daily","weekly","manual"} or not 0<=threshold<=100: raise ValueError("Unsupported schedule or threshold")
        if not self.get_asset(asset_id, actor) or not name.strip() or not expression.strip(): raise ValueError("Asset, name and expression are required")
        engine = "python_worker" if rule_type == "custom_python" else "platform_sql"
        with connect() as connection, connection.cursor() as cursor:
            if rule_id:
                cursor.execute("INSERT INTO fastdatagov.quality_rule_revisions (rule_id,version,snapshot,change_note,changed_by) SELECT id,version,to_jsonb(qr),'Rule update',%s FROM fastdatagov.quality_rules qr WHERE id=%s", (actor.email,rule_id))
                cursor.execute("UPDATE fastdatagov.quality_rules SET asset_id=%s,name=%s,rule_type=%s,expression=%s,threshold=%s,severity=%s,schedule=%s,execution_engine=%s,owner_email=coalesce(owner_email,%s),next_run_at=CASE %s WHEN 'hourly' THEN now()+interval '1 hour' WHEN 'daily' THEN now()+interval '1 day' WHEN 'weekly' THEN now()+interval '7 days' ELSE NULL END,version=version+1,updated_at=now() WHERE id=%s RETURNING id", (asset_id,name.strip(),rule_type,expression.strip(),threshold,severity,schedule,engine,actor.email,schedule,rule_id))
            else:
                cursor.execute("INSERT INTO fastdatagov.quality_rules (asset_id,name,rule_type,expression,threshold,severity,schedule,execution_engine,owner_email,next_run_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,CASE %s WHEN 'hourly' THEN now()+interval '1 hour' WHEN 'daily' THEN now()+interval '1 day' WHEN 'weekly' THEN now()+interval '7 days' ELSE NULL END) RETURNING id", (asset_id,name.strip(),rule_type,expression.strip(),threshold,severity,schedule,engine,actor.email,schedule))
            row=cursor.fetchone()
            if not row: raise ValueError("Rule does not exist")
            saved_id=row[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'quality.rule_saved','quality_rule',%s,jsonb_build_object('versioned',true))", (actor.subject,str(saved_id))); connection.commit()
        return next(r for r in self.quality_rules(actor) if r.id == saved_id)

    def queue_quality_run(self, rule_id, actor):
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id FROM fastdatagov.quality_rules WHERE id=%s AND enabled", (rule_id,))
            if not cursor.fetchone(): raise ValueError("Enabled rule does not exist")
            cursor.execute("SELECT id FROM fastdatagov.jobs WHERE kind='quality.run' AND status IN ('queued','running') AND (payload->>'rule_id')::bigint=%s ORDER BY id LIMIT 1",(rule_id,)); existing=cursor.fetchone()
            if existing: return existing[0]
            cursor.execute("INSERT INTO fastdatagov.jobs (kind,payload) VALUES ('quality.run',jsonb_build_object('rule_id',%s::bigint)) RETURNING id", (rule_id,)); job_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'quality.run_queued','quality_rule',%s)", (actor.subject,str(rule_id))); connection.commit(); return job_id

    def set_quality_enabled(self,rule_id,actor,enabled):
        visible={r.id for r in self.quality_rules(actor)}
        if rule_id not in visible: raise ValueError("Rule does not exist or is not visible")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fastdatagov.quality_rules SET enabled=%s,next_run_at=CASE WHEN %s THEN now() ELSE NULL END,updated_at=now() WHERE id=%s",(enabled,enabled,rule_id))
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'quality.rule_toggled','quality_rule',%s,jsonb_build_object('enabled',%s::boolean))",(actor.subject,str(rule_id),enabled)); connection.commit()

    def work_comments(self, item_id):
        return [WorkComment(row["id"],row["work_item_id"],row["author_email"],row["body"],str(row["created_at"])) for row in fetch_all("SELECT * FROM fastdatagov.work_item_comments WHERE work_item_id=%s ORDER BY created_at", (item_id,))]

    def add_work_comment(self, item_id, actor, body):
        if not body.strip(): raise ValueError("Comment is required")
        if not any(item.id==item_id for item in self.work_items(identity=actor)): raise ValueError("Work item does not exist or is not visible")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO fastdatagov.work_item_comments (work_item_id,author_email,body) VALUES (%s,%s,%s) RETURNING id", (item_id,actor.email,body.strip())); comment_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.work_item_events (work_item_id,actor_email,event_type,detail) VALUES (%s,%s,'commented',jsonb_build_object('comment_id',%s::bigint))", (item_id,actor.email,comment_id)); connection.commit()
        return next(c for c in self.work_comments(item_id) if c.id == comment_id)

    def certify_asset(self, asset_id, actor, status, expires_days, notes=""):
        if status not in {"certified", "verified", "rejected", "expired"}: raise ValueError("Unsupported certification status")
        if not self.get_asset(asset_id, actor): raise ValueError("Asset does not exist or is not visible")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id FROM fastdatagov.certifications WHERE asset_id=%s ORDER BY certified_at DESC LIMIT 1", (asset_id,)); prior=cursor.fetchone()
            cursor.execute("INSERT INTO fastdatagov.certifications (asset_id,status,certified_by,expires_at,notes,renewal_of_id) VALUES (%s,%s,%s,now()+(%s||' days')::interval,%s,%s)", (asset_id,status,actor.email,expires_days,notes,prior[0] if prior else None))
            cursor.execute("UPDATE fastdatagov.assets SET certification_status=%s,updated_at=now() WHERE id=%s", (status,asset_id))
            _recompute_trust(cursor,asset_id)
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'certification.decided','asset',%s,jsonb_build_object('status',%s::text,'expires_days',%s::integer))", (actor.subject,str(asset_id),status,expires_days))
            _queue_notifications(cursor,"certification.decided",actor.email,f"Certification {status}",f"Asset {asset_id} certification was recorded as {status}.",{"asset_id":asset_id,"status":status})
            connection.commit()

    def certify_product(self, product_id, actor, status, expires_days, notes=""):
        if status not in {"certified","verified","rejected","expired"}: raise ValueError("Unsupported certification status")
        product=next((p for p in self.products(actor) if p.id==product_id),None)
        if not product: raise ValueError("Product does not exist or is not visible")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id FROM fastdatagov.product_certifications WHERE product_id=%s ORDER BY certified_at DESC LIMIT 1",(product_id,)); prior=cursor.fetchone()
            cursor.execute("INSERT INTO fastdatagov.product_certifications (product_id,status,certified_by,expires_at,notes,renewal_of_id) VALUES (%s,%s,%s,now()+(%s||' days')::interval,%s,%s)",(product_id,status,actor.email,expires_days,notes,prior[0] if prior else None))
            cursor.execute("UPDATE fastdatagov.data_products SET certification_status=%s,updated_at=now() WHERE id=%s",(status,product_id))
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'certification.decided','data_product',%s,jsonb_build_object('status',%s::text))",(actor.subject,str(product_id),status))
            _queue_notifications(cursor,"certification.decided",product.owner,f"Product certification {status}",f"Data product {product.name} certification was recorded as {status}.",{"product_id":product_id,"status":status}); connection.commit()

    def assignments(self, scope_type="", scope_id=0):
        conditions=["true"]; params=[]
        if scope_type: conditions.append("scope_type=%s"); params.append(scope_type)
        if scope_id: conditions.append("scope_id=%s"); params.append(scope_id)
        rows=fetch_all("SELECT id,scope_type,scope_id,responsibility,assignee_email,coalesce(attested_at::text,'') attested_at,coalesce(attestation_expires_at::text,'') expires_at FROM fastdatagov.accountability_assignments WHERE "+" AND ".join(conditions)+" ORDER BY scope_type,scope_id,responsibility",tuple(params))
        return [AccountabilityAssignment(**row) for row in rows]

    def assign_accountability(self, actor, scope_type, scope_id, responsibility, email, expires_days=365):
        if scope_type not in {"domain", "product", "asset"} or responsibility not in {"owner", "steward"}: raise ValueError("Invalid accountability assignment")
        exists=(scope_type=="asset" and self.get_asset(scope_id,actor)) or (scope_type=="product" and any(p.id==scope_id for p in self.products(actor))) or (scope_type=="domain" and any(d.id==scope_id for d in self.domains()))
        if not exists or "@" not in email: raise ValueError("Accountability scope does not exist or email is invalid")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO fastdatagov.accountability_assignments (scope_type,scope_id,responsibility,assignee_email,assigned_by,attested_at,attestation_expires_at) VALUES (%s,%s,%s,%s,%s,now(),now()+(%s||' days')::interval) ON CONFLICT (scope_type,scope_id,responsibility,assignee_email) DO UPDATE SET attested_at=now(),attestation_expires_at=excluded.attestation_expires_at,assigned_by=excluded.assigned_by RETURNING id", (scope_type,scope_id,responsibility,email.strip(),actor.email,expires_days)); assignment_id=cursor.fetchone()[0]
            if scope_type == "asset": cursor.execute(f"UPDATE fastdatagov.assets SET {responsibility}_email=%s,updated_at=now() WHERE id=%s", (email.strip(),scope_id))
            elif scope_type == "product": cursor.execute(f"UPDATE fastdatagov.data_products SET {responsibility}_email=%s,updated_at=now() WHERE id=%s", (email.strip(),scope_id))
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,'accountability.assigned',%s,%s,jsonb_build_object('responsibility',%s::text,'email',%s::text))", (actor.subject,scope_type,str(scope_id),responsibility,email.strip())); connection.commit()
        return next(a for a in self.assignments(scope_type,scope_id) if a.id == assignment_id)

    def roles(self):
        return fetch_all("SELECT id,principal_type,principal_key,role,scope_type,coalesce(scope_key,'') scope_key FROM fastdatagov.role_bindings ORDER BY principal_type,principal_key,role")

    def save_role(self, actor, principal_type, principal_key, role, scope_type="global", scope_key=""):
        allowed={"consumer","steward","owner","engineer","governance_lead","admin"}
        if principal_type not in {"user","group"} or role not in allowed or scope_type!="global": raise ValueError("Only global application role bindings are supported; use accountability assignments for domain/asset responsibility")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO fastdatagov.role_bindings (principal_type,principal_key,role,scope_type,scope_key) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (principal_type,principal_key,role,scope_type,scope_key) DO UPDATE SET principal_key=excluded.principal_key RETURNING id", (principal_type,principal_key.strip(),role,scope_type,scope_key.strip())); role_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'role.created','role_binding',%s)", (actor.subject,str(role_id))); connection.commit()
        return next(r for r in self.roles() if r["id"] == role_id)

    def delete_role(self,actor,role_id):
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM fastdatagov.role_bindings WHERE id=%s RETURNING id",(role_id,))
            if not cursor.fetchone(): raise ValueError("Role binding does not exist")
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'role.removed','role_binding',%s)",(actor.subject,str(role_id))); connection.commit()

    def jobs(self, limit=50):
        return [JobStatus(row["id"],row["kind"],row["status"],row["attempts"],str(row["run_after"]),row.get("last_error") or "") for row in fetch_all("SELECT id,kind,status,attempts,run_after,last_error FROM fastdatagov.jobs ORDER BY created_at DESC LIMIT %s", (limit,))]

    def pilot_metrics(self):
        current=self.metrics()
        execute("UPDATE fastdatagov.pilot_metrics SET current_value=%s,measured_at=now() WHERE key='catalog_coverage'", (current["catalog_coverage"],))
        execute("UPDATE fastdatagov.pilot_metrics SET current_value=%s,measured_at=now() WHERE key='accountability_coverage'", (current["accountability_pct"],))
        execute("UPDATE fastdatagov.pilot_metrics SET current_value=(SELECT CASE WHEN count(*)=0 THEN 0 ELSE 100.0*count(DISTINCT qr.asset_id)/count(DISTINCT a.id) END FROM fastdatagov.assets a LEFT JOIN fastdatagov.quality_rules qr ON qr.asset_id=a.id AND qr.enabled WHERE a.deleted_at IS NULL),measured_at=now() WHERE key='quality_rule_coverage'")
        execute("UPDATE fastdatagov.pilot_metrics SET current_value=(SELECT percentile_disc(.5) WITHIN GROUP (ORDER BY extract(epoch FROM (updated_at-created_at))/3600) FROM fastdatagov.work_items WHERE kind IN ('access','certification') AND status IN ('approved','resolved')),measured_at=now() WHERE key='time_to_trusted_data'")
        execute("UPDATE fastdatagov.pilot_metrics SET current_value=(SELECT count(*) FROM fastdatagov.users WHERE last_seen_at>=now()-interval '7 days'),measured_at=now() WHERE key='weekly_active_users'")
        rows=fetch_all("SELECT key,label,unit,baseline::float,target::float,current_value::float,coalesce(measured_at::text,'') measured_at,notes FROM fastdatagov.pilot_metrics ORDER BY id")
        return [PilotMetric(**row) for row in rows]

    def workflow_definitions(self):
        return fetch_all("SELECT kind,display_name,due_days,coalesce(approval_role,'') approval_role,enabled,configuration FROM fastdatagov.workflow_definitions ORDER BY id")

    def save_workflow_definition(self, actor, kind, due_days, approval_role, enabled):
        if kind not in {"quality","certification","metadata","access","attestation"} or due_days < 1: raise ValueError("Invalid workflow definition")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fastdatagov.workflow_definitions SET due_days=%s,approval_role=%s,enabled=%s,updated_by=%s,updated_at=now() WHERE kind=%s RETURNING kind",(due_days,approval_role or None,enabled,actor.email,kind)); row=cursor.fetchone()
            if not row: raise ValueError("Workflow definition does not exist")
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'workflow.definition_updated','workflow_definition',%s)",(actor.subject,kind)); connection.commit()
        return next(row for row in self.workflow_definitions() if row["kind"]==kind)

    def notification_channels(self):
        return fetch_all("SELECT id,key,channel_type,endpoint_ref,events,enabled,updated_at::text updated_at FROM fastdatagov.notification_channels ORDER BY key")

    def save_notification_channel(self, actor, key, channel_type, endpoint_ref, events, enabled=True):
        if channel_type not in {"email","teams","slack","webhook"} or not key.strip() or not endpoint_ref.startswith("env:"): raise ValueError("Notification channels require a key, supported type and env: secret reference")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO fastdatagov.notification_channels (key,channel_type,endpoint_ref,events,enabled,created_by) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (key) DO UPDATE SET channel_type=excluded.channel_type,endpoint_ref=excluded.endpoint_ref,events=excluded.events,enabled=excluded.enabled,updated_at=now() RETURNING id",(key.strip(),channel_type,endpoint_ref,events,enabled,actor.email)); channel_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'notification.channel_saved','notification_channel',%s)",(actor.subject,key.strip())); connection.commit()
        return next(row for row in self.notification_channels() if row["id"]==channel_id)

    def connection_details(self):
        return fetch_all("SELECT c.key,c.name,p.adapter_type,coalesce(c.credential_ref,'') credential_ref,c.config,c.status,coalesce(c.last_sync_at::text,'Never') last_sync,coalesce(c.last_error,'') last_error FROM fastdatagov.connections c JOIN fastdatagov.platforms p ON p.id=c.platform_id ORDER BY c.name")

    def save_connection(self, actor, key, name, adapter_type, credential_ref, config):
        if adapter_type not in {"snowflake","fabric","databricks","demo"} or (credential_ref and not credential_ref.startswith("env:")): raise ValueError("Invalid adapter or credential reference")
        if _contains_secret(config): raise ValueError("Connection configuration cannot contain secret values")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO fastdatagov.platforms (key,name,adapter_type) VALUES (%s,%s,%s) ON CONFLICT (key) DO UPDATE SET name=excluded.name,adapter_type=excluded.adapter_type RETURNING id",(adapter_type,adapter_type.title(),adapter_type)); platform_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.connections (platform_id,key,name,credential_ref,config) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (key) DO UPDATE SET platform_id=excluded.platform_id,name=excluded.name,credential_ref=excluded.credential_ref,config=excluded.config,updated_at=now()",(platform_id,key.strip(),name.strip(),credential_ref or None,Jsonb(config)))
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'connection.saved','connection',%s)",(actor.subject,key.strip())); connection.commit()
        return next(c for c in self.connection_details() if c["key"]==key.strip())

    def queue_adapter_job(self, actor, key, kind):
        if kind not in {"adapter.sync","adapter.health"}: raise ValueError("Invalid adapter job")
        row=fetch_one("SELECT id FROM fastdatagov.connections WHERE key=%s",(key,))
        if not row: raise ValueError("Connection does not exist")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id FROM fastdatagov.jobs WHERE kind=%s AND status IN ('queued','running') AND (payload->>'connection_id')::bigint=%s ORDER BY id LIMIT 1",(kind,row["id"])); existing=cursor.fetchone()
            if existing:return existing[0]
            cursor.execute("INSERT INTO fastdatagov.jobs (kind,payload) VALUES (%s,jsonb_build_object('connection_id',%s::bigint)) RETURNING id",(kind,row["id"])); job_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'adapter.job_queued','connection',%s)",(actor.subject,key)); connection.commit(); return job_id

    def principal_aliases(self):
        return fetch_all("SELECT id,identity_principal_type,identity_key,platform_key,source_principal_key FROM fastdatagov.principal_aliases ORDER BY platform_key,identity_key")

    def save_principal_alias(self, actor, identity_principal_type, identity_key, platform_key, source_principal_key):
        if identity_principal_type not in {"user","group"} or not all(v.strip() for v in (identity_key,platform_key,source_principal_key)): raise ValueError("Invalid principal alias")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO fastdatagov.principal_aliases (identity_principal_type,identity_key,platform_key,source_principal_key,created_by) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (identity_principal_type,identity_key,platform_key,source_principal_key) DO UPDATE SET created_by=excluded.created_by RETURNING id",(identity_principal_type,identity_key.strip(),platform_key.strip(),source_principal_key.strip(),actor.email)); alias_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'principal.alias_saved','principal_alias',%s)",(actor.subject,str(alias_id))); connection.commit()
        return next(row for row in self.principal_aliases() if row["id"]==alias_id)

    def delete_principal_alias(self,actor,alias_id):
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM fastdatagov.principal_aliases WHERE id=%s RETURNING id",(alias_id,))
            if not cursor.fetchone(): raise ValueError("Principal alias does not exist")
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'principal.alias_removed','principal_alias',%s)",(actor.subject,str(alias_id))); connection.commit()

    def queue_tag_writeback(self, actor, asset_id, tags):
        asset=self.get_asset(asset_id,actor)
        if not asset: raise ValueError("Asset does not exist or is not visible")
        row=fetch_one("SELECT connection_id,external_id FROM fastdatagov.assets WHERE id=%s",(asset_id,))
        if not tags: raise ValueError("At least one native tag is required")
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("INSERT INTO fastdatagov.jobs (kind,payload) VALUES ('adapter.tags',%s) RETURNING id",(Jsonb({"connection_id":row["connection_id"],"asset_external_id":row["external_id"],"tags":tags}),)); job_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key) VALUES (%s,'adapter.tag_writeback_queued','asset',%s)",(actor.subject,str(asset_id))); connection.commit(); return job_id


@lru_cache(maxsize=1)
def repository() -> GovernanceRepository:
    if settings().repository_mode == "postgres":
        return PostgresRepository()
    return DemoRepository()
