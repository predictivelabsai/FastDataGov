from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from fastdatagov.adapters.base import (
    AdapterHealth,
    AdapterNotConfigured,
    FieldRecord,
    PlatformAdapter,
    QualityResultRecord,
    QualityRuleSpec,
    SyncPage,
    TagRecord,
)


class ContractReadyAdapter(PlatformAdapter):
    """Complete contract surface for adapters awaiting tenant credentials."""

    configuration_help = "Configure endpoint and service-principal credentials."

    def _configured(self) -> bool:
        return bool(self.connection.settings.get("endpoint") and self.connection.credential_ref)

    def connect(self) -> None:
        if not self._configured():
            raise AdapterNotConfigured(self.configuration_help)
        raise AdapterNotConfigured(f"{self.display_name} transport is contract-ready; install the tenant implementation package.")

    def close(self) -> None:
        return None

    def health(self) -> AdapterHealth:
        status = "ready" if not self._configured() else "configuration-required"
        return AdapterHealth(status, self.configuration_help, checked_at=datetime.now(timezone.utc))

    def _unavailable(self):
        raise AdapterNotConfigured(self.configuration_help)

    def discover_assets(self, cursor=None) -> SyncPage:
        self._unavailable()

    def discover_fields(self, asset_external_ids: list[str]) -> Iterator[FieldRecord]:
        self._unavailable()
        yield from ()

    def discover_lineage(self, cursor=None) -> SyncPage:
        self._unavailable()

    def discover_tags(self, asset_external_ids: list[str]) -> Iterator[TagRecord]:
        self._unavailable()
        yield from ()

    def discover_usage(self, cursor=None) -> SyncPage:
        self._unavailable()

    def execute_quality(self, rule: QualityRuleSpec) -> QualityResultRecord:
        self._unavailable()

    def write_tags(self, asset_external_id: str, tags: dict[str, str]) -> None:
        self._unavailable()
