from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Iterator

from fastdatagov.adapters.base import (
    AdapterCapabilities,
    AdapterError,
    AdapterHealth,
    AdapterNotConfigured,
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

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*){0,2}$")
FORBIDDEN_SQL = re.compile(r"(;|--|/\*|\b(ALTER|CALL|COPY|CREATE|DELETE|DROP|GRANT|INSERT|MERGE|PUT|REMOVE|REVOKE|TRUNCATE|UPDATE)\b)", re.IGNORECASE)
UNIQUENESS_EXPRESSION=re.compile(r"^COUNT\(\*\)\s*=\s*COUNT\(DISTINCT\s+([A-Za-z_][A-Za-z0-9_$]*)\)$",re.IGNORECASE)


class SnowflakeAdapter(PlatformAdapter):
    key = "snowflake"
    display_name = "Snowflake"
    capabilities = AdapterCapabilities("full", "full", "full", "read/write", "full", "governance tags", "full")

    def __init__(self, connection):
        super().__init__(connection)
        self._connection = None

    def connect(self) -> None:
        try:
            import snowflake.connector
        except ImportError as exc:
            raise AdapterNotConfigured("Install FastDataGov with the 'snowflake' extra.") from exc
        required = ("account", "user", "warehouse", "role")
        missing = [key for key in required if not self.connection.settings.get(key)]
        if missing:
            raise AdapterNotConfigured("Missing Snowflake settings: " + ", ".join(missing))
        kwargs = {key: self.connection.settings[key] for key in required}
        if self.connection.settings.get("password"):
            kwargs["password"] = self.connection.settings["password"]
        elif self.connection.settings.get("private_key"):
            kwargs["private_key"] = self.connection.settings["private_key"]
        else:
            raise AdapterNotConfigured("Provide a password or injected private key.")
        kwargs["application"] = "FastDataGov"
        kwargs["session_parameters"] = {"QUERY_TAG": "fastdatagov"}
        self._connection = snowflake.connector.connect(**kwargs)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _rows(self, sql: str, params: tuple = ()) -> list[dict]:
        if self._connection is None:
            raise AdapterError("Snowflake adapter is not connected")
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [column[0].lower() for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def health(self) -> AdapterHealth:
        started = time.monotonic()
        try:
            self._rows("SELECT CURRENT_ACCOUNT() AS account")
            latency = round((time.monotonic() - started) * 1000)
            return AdapterHealth("healthy", "Snowflake connection and governance role are available.", latency, datetime.now(timezone.utc))
        except Exception as exc:
            return AdapterHealth("unhealthy", str(exc), checked_at=datetime.now(timezone.utc))

    def discover_assets(self, cursor=None) -> SyncPage:
        changed_after = (cursor or {}).get("last_altered", "1970-01-01T00:00:00+00:00")
        rows = self._rows(
            """
            SELECT table_catalog, table_schema, table_name, table_type, comment,
                   last_altered, row_count, bytes, deleted
            FROM snowflake.account_usage.tables
            WHERE last_altered > %s::timestamp_tz
              AND table_schema NOT IN ('INFORMATION_SCHEMA')
            ORDER BY last_altered, table_catalog, table_schema, table_name
            """,
            (changed_after,),
        )
        records = []
        for row in rows:
            qualified = ".".join([row["table_catalog"], row["table_schema"], row["table_name"]])
            records.append(AssetRecord(qualified, qualified, row["table_name"], row["table_type"].lower().replace(" ", "_"), row.get("comment") or "", native_metadata={"row_count": row.get("row_count"), "bytes": row.get("bytes"), "last_altered": str(row.get("last_altered"))}, observed_at=datetime.now(timezone.utc),deleted=row.get("deleted") is not None))
        next_cursor = {"last_altered": str(max((row["last_altered"] for row in rows), default=changed_after))}
        return SyncPage(records, next_cursor)

    def discover_fields(self, asset_external_ids: list[str]) -> Iterator[FieldRecord]:
        wanted = set(asset_external_ids)
        rows = self._rows(
            """
            SELECT table_catalog, table_schema, table_name, column_name, ordinal_position,
                   data_type, is_nullable, comment
            FROM snowflake.account_usage.columns
            WHERE deleted IS NULL
            ORDER BY table_catalog, table_schema, table_name, ordinal_position
            """
        )
        for row in rows:
            asset_id = ".".join([row["table_catalog"], row["table_schema"], row["table_name"]])
            if asset_id not in wanted:
                continue
            yield FieldRecord(asset_id, f"{asset_id}.{row['column_name']}", row["column_name"], row["data_type"], row["ordinal_position"], row["is_nullable"] == "YES", row.get("comment") or "")

    def discover_lineage(self, cursor=None) -> SyncPage:
        rows = self._rows(
            """
            SELECT referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS target_id,
                   referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS source_id,
                   dependency_type
            FROM snowflake.account_usage.object_dependencies
            WHERE referenced_object_domain IN ('TABLE', 'VIEW')
              AND referencing_object_domain IN ('TABLE', 'VIEW')
            """
        )
        records = [LineageRecord(row["source_id"], row["target_id"], row["dependency_type"].lower(), "native", 1.0) for row in rows]
        changed_after=(cursor or {}).get("access_after","1970-01-01T00:00:00+00:00")
        column_rows=self._rows(
            """
            SELECT DISTINCT src.value:objectName::string AS source_id,
                   tgt.value:objectName::string AS target_id,
                   src.value:columnName::string AS source_field,
                   tgt_col.value:columnName::string AS target_field
            FROM snowflake.account_usage.access_history ah,
                 LATERAL FLATTEN(input => ah.objects_modified) tgt,
                 LATERAL FLATTEN(input => tgt.value:columns) tgt_col,
                 LATERAL FLATTEN(input => coalesce(tgt_col.value:baseSources,tgt_col.value:directSources)) src
            WHERE ah.query_start_time > %s::timestamp_tz
              AND tgt.value:objectDomain::string IN ('Table','View')
            """,(changed_after,)
        )
        records.extend(LineageRecord(row["source_id"],row["target_id"],"query transformation","query_history",.95,row.get("source_field") or "",row.get("target_field") or "") for row in column_rows if row.get("source_id") and row.get("target_id"))
        now=datetime.now(timezone.utc).isoformat()
        return SyncPage(records, {"observed_at":now,"access_after":now})

    def discover_tags(self, asset_external_ids: list[str]) -> Iterator[TagRecord]:
        wanted = set(asset_external_ids)
        rows = self._rows("SELECT object_database, object_schema, object_name, tag_database, tag_schema, tag_name, tag_value FROM snowflake.account_usage.tag_references WHERE domain IN ('TABLE', 'VIEW')")
        for row in rows:
            asset_id = ".".join([row["object_database"], row["object_schema"], row["object_name"]])
            if asset_id in wanted:
                key = ".".join([row["tag_database"], row["tag_schema"], row["tag_name"]])
                yield TagRecord(asset_id, key, row["tag_value"], "snowflake")

    def discover_usage(self, cursor=None) -> SyncPage:
        start = (cursor or {}).get("period_start", "1970-01-01T00:00:00+00:00")
        rows = self._rows(
            """
            SELECT value:objectName::string AS asset_external_id,
                   count(*) AS query_count, count(DISTINCT user_name) AS distinct_users,
                   min(query_start_time) AS period_start, max(query_start_time) AS period_end
            FROM snowflake.account_usage.access_history,
                 lateral flatten(input => base_objects_accessed)
            WHERE query_start_time > %s::timestamp_tz
            GROUP BY asset_external_id
            """,
            (start,),
        )
        records = [UsageRecord(row["asset_external_id"], row["query_count"], row["distinct_users"], row["period_start"], row["period_end"]) for row in rows if row.get("asset_external_id")]
        return SyncPage(records, {"period_start": datetime.now(timezone.utc).isoformat()})

    def discover_grants(self, asset_external_ids: list[str]) -> Iterator[GrantRecord]:
        wanted = set(asset_external_ids)
        rows = self._rows(
            """
            WITH RECURSIVE object_grants AS (
                SELECT iff(contains(name,'.'),name,concat_ws('.',table_catalog,table_schema,name)) asset_external_id,
                       grantee_name,granted_to,privilege
                FROM snowflake.account_usage.grants_to_roles
                WHERE deleted_on IS NULL AND granted_on IN ('TABLE', 'VIEW', 'DYNAMIC TABLE')
                  AND privilege IN ('SELECT', 'OWNERSHIP', 'REFERENCES')
            ), expanded(asset_external_id,grantee_name,granted_to,privilege) AS (
                SELECT asset_external_id,grantee_name,granted_to,privilege FROM object_grants
                UNION
                SELECT e.asset_external_id,h.grantee_name,h.granted_to,e.privilege
                FROM expanded e JOIN snowflake.account_usage.grants_to_roles h
                  ON h.name=e.grantee_name AND h.granted_on='ROLE' AND h.deleted_on IS NULL
            )
            SELECT DISTINCT asset_external_id,grantee_name,granted_to,privilege FROM expanded
            """
        )
        for row in rows:
            if row["asset_external_id"] in wanted:
                principal_type="user" if row.get("granted_to")=="USER" else "group"
                yield GrantRecord(row["asset_external_id"], principal_type, row["grantee_name"], "discover", "snowflake_role_grant")

    @staticmethod
    def _validate_quality_rule(rule: QualityRuleSpec) -> None:
        if not IDENTIFIER.fullmatch(rule.asset_external_id):
            raise AdapterError("Quality asset identifier is invalid")
        if not rule.expression.strip() or FORBIDDEN_SQL.search(rule.expression):
            raise AdapterError("Quality expression contains an unsafe token")

    def execute_quality(self, rule: QualityRuleSpec) -> QualityResultRecord:
        self._validate_quality_rule(rule)
        if self._connection is None:
            raise AdapterError("Snowflake adapter is not connected")
        with self._connection.cursor() as cursor:
            cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {int(rule.statement_timeout_seconds)}")
            quality_role=self.connection.settings.get("quality_role",""); quality_warehouse=self.connection.settings.get("quality_warehouse","")
            if quality_role:
                if not IDENTIFIER.fullmatch(quality_role): raise AdapterError("Quality role identifier is invalid")
                cursor.execute(f"USE ROLE {quality_role}")
            if quality_warehouse:
                if not IDENTIFIER.fullmatch(quality_warehouse): raise AdapterError("Quality warehouse identifier is invalid")
                cursor.execute(f"USE WAREHOUSE {quality_warehouse}")
            uniqueness=UNIQUENESS_EXPRESSION.fullmatch(rule.expression.strip()) if rule.rule_type=="uniqueness" else None
            if uniqueness:
                column=uniqueness.group(1)
                cursor.execute(f"SELECT COUNT(*) AS rows_evaluated, COUNT(*)-COUNT(DISTINCT {column}) AS failed_rows FROM {rule.asset_external_id}")
                rows_evaluated,failed_rows=cursor.fetchone()
            else:
                cursor.execute(f"SELECT COUNT(*) AS rows_evaluated, COUNT_IF(NOT ({rule.expression})) AS failed_rows FROM {rule.asset_external_id}")
                rows_evaluated, failed_rows = cursor.fetchone()
        score = 100.0 if not rows_evaluated else (rows_evaluated - failed_rows) / rows_evaluated * 100
        status = "passed" if score >= rule.threshold else "failed"
        return QualityResultRecord(status, score, float(failed_rows), rows_evaluated, f"{failed_rows} of {rows_evaluated} rows failed", {"threshold": rule.threshold})

    def write_tags(self, asset_external_id: str, tags: dict[str, str]) -> None:
        if not IDENTIFIER.fullmatch(asset_external_id):
            raise AdapterError("Asset identifier is invalid")
        if self._connection is None:
            raise AdapterError("Snowflake adapter is not connected")
        with self._connection.cursor() as cursor:
            writeback_role=self.connection.settings.get("writeback_role","")
            if writeback_role:
                if not IDENTIFIER.fullmatch(writeback_role): raise AdapterError("Write-back role identifier is invalid")
                cursor.execute(f"USE ROLE {writeback_role}")
            for tag_name, tag_value in tags.items():
                if not IDENTIFIER.fullmatch(tag_name):
                    raise AdapterError(f"Tag identifier is invalid: {tag_name}")
                safe_value = tag_value.replace("'", "''")
                cursor.execute(f"ALTER TABLE {asset_external_id} SET TAG {tag_name} = '{safe_value}'")
