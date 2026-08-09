from __future__ import annotations

import inspect

import pytest

from fastdatagov.adapters.base import AdapterError, AdapterNotConfigured, ConnectionConfig, PlatformAdapter, QualityRuleSpec
from fastdatagov.adapters.demo import DemoAdapter
from fastdatagov.adapters.registry import adapter_registry, build_adapter
from fastdatagov.adapters.snowflake import SnowflakeAdapter
from fastdatagov.jobs.runtime import _collect_pages
from fastdatagov.adapters.base import SyncPage


def test_registry_contains_priority_platforms_and_demo():
    assert set(adapter_registry) == {"demo", "snowflake", "fabric", "databricks"}


@pytest.mark.parametrize("adapter_key", ["demo", "snowflake", "fabric", "databricks"])
def test_adapter_contract_is_complete(adapter_key):
    adapter_class = adapter_registry[adapter_key]
    assert not inspect.isabstract(adapter_class)
    for method in (
        "connect", "close", "health", "discover_assets", "discover_fields",
        "discover_lineage", "discover_tags", "discover_usage", "discover_grants", "execute_quality", "write_tags",
    ):
        assert callable(getattr(adapter_class, method))


def test_demo_adapter_exercises_full_contract():
    adapter = DemoAdapter(ConnectionConfig("demo", "Demo", {}))
    with adapter:
        assert adapter.health().status == "healthy"
        assets = adapter.discover_assets()
        assert len(assets.records) == 12
        fields = list(adapter.discover_fields([assets.records[0].external_id]))
        assert fields
        assert adapter.discover_lineage().records
        assert list(adapter.discover_tags(["1"]))
        assert adapter.discover_usage().records
        assert list(adapter.discover_grants(["1"]))
        result = adapter.execute_quality(QualityRuleSpec("1", "completeness", "CUSTOMER_ID IS NOT NULL", 95))
        assert result.status == "passed"
        adapter.write_tags("1", {"reviewed": "true"})
        assert any(tag.key == "reviewed" for tag in adapter.discover_tags(["1"]))
    assert adapter.connected is False


@pytest.mark.parametrize("adapter_key", ["fabric", "databricks"])
def test_contract_ready_adapters_report_clear_configuration_state(adapter_key):
    adapter = build_adapter(adapter_key, ConnectionConfig(adapter_key, adapter_key.title(), {}))
    assert adapter.health().status == "ready"
    with pytest.raises(AdapterNotConfigured):
        adapter.discover_assets()


def test_unknown_adapter_is_rejected():
    with pytest.raises(ValueError, match="Unknown adapter"):
        build_adapter("unknown", ConnectionConfig("x", "X", {}))


@pytest.mark.parametrize(
    "asset,expression",
    [
        ("PROD.CORE.CUSTOMER; DROP TABLE X", "CUSTOMER_ID IS NOT NULL"),
        ("PROD.CORE.CUSTOMER", "1=1; DELETE FROM CUSTOMER"),
        ("PROD.CORE.CUSTOMER", "-- always true"),
    ],
)
def test_snowflake_quality_rule_validation_rejects_unsafe_sql(asset, expression):
    rule = QualityRuleSpec(asset, "custom", expression, 95)
    with pytest.raises(AdapterError):
        SnowflakeAdapter._validate_quality_rule(rule)


def test_snowflake_quality_rule_validation_accepts_predicate():
    SnowflakeAdapter._validate_quality_rule(
        QualityRuleSpec("PROD.CORE.CUSTOMER", "completeness", "CUSTOMER_ID IS NOT NULL", 99.9)
    )


def test_adapter_runtime_collects_all_pages_and_rejects_stalled_cursor():
    def page(cursor):
        index=cursor.get("page",0)
        return SyncPage([index],{"page":index+1},complete=index==2)
    assert _collect_pages(page,{}).records==[0,1,2]
    with pytest.raises(ValueError,match="without advancing"):
        _collect_pages(lambda cursor:SyncPage([],cursor,complete=False),{})


def test_snowflake_maps_documented_column_lineage_and_transitive_grants():
    class FixtureSnowflake(SnowflakeAdapter):
        def _rows(self,sql,params=()):
            if "object_dependencies" in sql: return [{"source_id":"DB.RAW.SOURCE","target_id":"DB.CURATED.TARGET","dependency_type":"BY_NAME"}]
            if "objects_modified" in sql: return [{"source_id":"DB.RAW.SOURCE","target_id":"DB.CURATED.TARGET","source_field":"ID","target_field":"SOURCE_ID"}]
            if "WITH RECURSIVE object_grants" in sql: return [{"asset_external_id":"DB.CURATED.TARGET","grantee_name":"ANALYST_ROLE","granted_to":"ACCOUNT ROLE","privilege":"SELECT"}]
            return []
    adapter=FixtureSnowflake(ConnectionConfig("snowflake","Snowflake",{}))
    edges=adapter.discover_lineage().records
    assert any(edge.source_field=="ID" and edge.target_field=="SOURCE_ID" for edge in edges)
    grants=list(adapter.discover_grants(["DB.CURATED.TARGET"]))
    assert grants[0].principal_key=="ANALYST_ROLE" and grants[0].principal_type=="group"
