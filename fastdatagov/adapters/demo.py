from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator

from fastdatagov.adapters.base import (
    AdapterCapabilities,
    AdapterHealth,
    AssetRecord,
    FieldRecord,
    GrantRecord,
    LineageRecord,
    PlatformAdapter,
    QualityResultRecord,
    QualityRuleSpec,
    SyncPage,
    TagRecord,
    UsageRecord,
)
from fastdatagov.synthetic.data import ASSETS, LINEAGE


class DemoAdapter(PlatformAdapter):
    key = "demo"
    display_name = "Deterministic demo"
    capabilities = AdapterCapabilities("full", "full", "full", "read/write", "full", "business tags", "public")

    def __init__(self, connection):
        super().__init__(connection)
        self.connected = False
        self._tag_writes: dict[str, dict[str, str]] = {}

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    def health(self) -> AdapterHealth:
        return AdapterHealth("healthy" if self.connected else "ready", "Deterministic local corpus is available.", 1, datetime.now(timezone.utc))

    def discover_assets(self, cursor=None) -> SyncPage:
        records = [AssetRecord(str(a.id), a.qualified_name, a.name, a.asset_type, a.description, a.source_url, {"platform": a.platform}, datetime.now(timezone.utc)) for a in ASSETS]
        return SyncPage(records, {"observed_at": datetime.now(timezone.utc).isoformat()})

    def discover_fields(self, asset_external_ids: list[str]) -> Iterator[FieldRecord]:
        wanted = set(asset_external_ids)
        for asset in ASSETS:
            if str(asset.id) not in wanted:
                continue
            for ordinal, column in enumerate(asset.fields, 1):
                yield FieldRecord(str(asset.id), f"{asset.id}:{column.name}", column.name, column.data_type, ordinal, column.nullable, column.description, {"classification": column.classification})

    def discover_lineage(self, cursor=None) -> SyncPage:
        records = [LineageRecord(str(edge.source_id), str(edge.target_id), edge.operation, edge.evidence_type, edge.confidence) for edge in LINEAGE]
        return SyncPage(records, {"observed_at": datetime.now(timezone.utc).isoformat()})

    def discover_tags(self, asset_external_ids: list[str]) -> Iterator[TagRecord]:
        wanted = set(asset_external_ids)
        for asset in ASSETS:
            if str(asset.id) in wanted:
                for tag in asset.tags:
                    yield TagRecord(str(asset.id), tag, "true", "demo")
        for asset_id, tags in self._tag_writes.items():
            if asset_id in wanted:
                for key, value in tags.items():
                    yield TagRecord(asset_id, key, value, "fastdatagov")

    def discover_usage(self, cursor=None) -> SyncPage:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30)
        return SyncPage([UsageRecord(str(asset.id), asset.usage_30d, max(1, asset.usage_30d // 14), start, end) for asset in ASSETS], {"period_end": end.isoformat()})

    def discover_grants(self, asset_external_ids: list[str]) -> Iterator[GrantRecord]:
        for asset_id in asset_external_ids:
            yield GrantRecord(asset_id, "public", "*", "discover", "demo")

    def execute_quality(self, rule: QualityRuleSpec) -> QualityResultRecord:
        asset = next((a for a in ASSETS if str(a.id) == rule.asset_external_id), None)
        score = asset.quality_score if asset else 0.0
        return QualityResultRecord("passed" if score >= rule.threshold else "failed", score, score, 10_000, f"Demo score {score:.1f}% against threshold {rule.threshold:.1f}%")

    def write_tags(self, asset_external_id: str, tags: dict[str, str]) -> None:
        self._tag_writes.setdefault(asset_external_id, {}).update(tags)
