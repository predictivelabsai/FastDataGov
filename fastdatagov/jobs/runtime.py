from __future__ import annotations

import os
from datetime import date, datetime, timezone

from psycopg.types.json import Jsonb

from fastdatagov.adapters import build_adapter
from fastdatagov.adapters.base import ConnectionConfig, QualityRuleSpec, SyncPage
from fastdatagov.config import settings
from fastdatagov.db import connect, fetch_one


def _collect_pages(fetch_page, cursor: dict | None, maximum_pages: int = 1000):
    records=[]; current=cursor or {}; final=current
    for _ in range(maximum_pages):
        page=fetch_page(current); records.extend(page.records); final=page.next_cursor
        if page.complete:
            return SyncPage(records,final,True)
        if final==current: raise ValueError("Adapter returned an incomplete page without advancing its cursor")
        current=final
    raise ValueError("Adapter pagination exceeded the safety limit")


def _adapter_for_connection(connection_id: int):
    row = fetch_one(
        """
        SELECT c.id, c.key, c.name, c.credential_ref, c.config, p.adapter_type
        FROM fastdatagov.connections c
        JOIN fastdatagov.platforms p ON p.id=c.platform_id
        WHERE c.id=%s
        """,
        (connection_id,),
    )
    if not row:
        raise ValueError(f"Connection {connection_id} does not exist")
    config = dict(row["config"] or {})
    credential_ref = row.get("credential_ref") or ""
    if credential_ref.startswith("env:"):
        variable = credential_ref.removeprefix("env:")
        value = os.getenv(variable, "")
        if value:
            if config.get("credential_type")=="private_key":
                try:
                    from cryptography.hazmat.primitives import serialization
                    key=serialization.load_pem_private_key(value.encode(),password=None)
                    config["private_key"]=key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
                except Exception as exc:
                    raise ValueError("Configured private-key credential could not be loaded") from exc
            else:
                config["password"] = value
    return build_adapter(row["adapter_type"], ConnectionConfig(row["key"], row["name"], config, credential_ref))


def sync_connection(connection_id: int) -> dict:
    adapter = _adapter_for_connection(connection_id)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT sync_cursor FROM fastdatagov.connections WHERE id=%s", (connection_id,))
        sync_cursor = cursor.fetchone()[0] or {}
        cursor.execute(
            "INSERT INTO fastdatagov.sync_runs (connection_id, status, cursor_before) VALUES (%s, 'running', %s) RETURNING id",
            (connection_id, Jsonb(sync_cursor)),
        )
        sync_run_id = cursor.fetchone()[0]
        connection.commit()

    counts = {"assets": 0, "fields": 0, "lineage": 0, "tags": 0, "usage": 0, "grants": 0}
    try:
        with adapter:
            asset_page = _collect_pages(adapter.discover_assets,sync_cursor.get("assets"))
            external_ids = [record.external_id for record in asset_page.records]
            with connect() as connection, connection.cursor() as cursor:
                for record in asset_page.records:
                    cursor.execute(
                        """
                        INSERT INTO fastdatagov.assets
                            (connection_id, external_id, qualified_name, name, asset_type,
                             platform_key, description, source_url, native_metadata, last_observed_at, refreshed_at,deleted_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,coalesce(%s,now()),now(),%s)
                        ON CONFLICT (connection_id, external_id) DO UPDATE SET
                            qualified_name=excluded.qualified_name, name=excluded.name,
                            asset_type=excluded.asset_type, description=excluded.description,
                            source_url=excluded.source_url, native_metadata=excluded.native_metadata,
                            last_observed_at=excluded.last_observed_at, refreshed_at=now(),
                            deleted_at=excluded.deleted_at, updated_at=now()
                        """,
                        (connection_id, record.external_id, record.qualified_name, record.name,
                         record.asset_type, adapter.key, record.description, record.source_url,
                         Jsonb(record.native_metadata), record.observed_at,datetime.now(timezone.utc) if record.deleted else None),
                    )
                    counts["assets"] += 1

                for field in adapter.discover_fields(external_ids):
                    cursor.execute("SELECT id FROM fastdatagov.assets WHERE connection_id=%s AND external_id=%s", (connection_id, field.asset_external_id))
                    asset_row = cursor.fetchone()
                    if not asset_row:
                        continue
                    cursor.execute(
                        """
                        INSERT INTO fastdatagov.asset_fields
                            (asset_id, external_id, name, ordinal, data_type, nullable, description, native_metadata)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (asset_id, external_id) DO UPDATE SET
                            name=excluded.name, ordinal=excluded.ordinal, data_type=excluded.data_type,
                            nullable=excluded.nullable, description=excluded.description,
                            native_metadata=excluded.native_metadata
                        """,
                        (asset_row[0], field.external_id, field.name, field.ordinal, field.data_type,
                         field.nullable, field.description, Jsonb(field.native_metadata)),
                    )
                    counts["fields"] += 1

                cursor.execute("SELECT external_id FROM fastdatagov.assets WHERE connection_id=%s AND deleted_at IS NULL",(connection_id,))
                governed_external_ids=[row[0] for row in cursor.fetchall()]
                cursor.execute("DELETE FROM fastdatagov.asset_tags atag USING fastdatagov.assets a WHERE a.id=atag.asset_id AND a.connection_id=%s AND atag.source<>'fastdatagov'",(connection_id,))
                tag_records = adapter.discover_tags(governed_external_ids)
                for tag in tag_records:
                    cursor.execute("SELECT id FROM fastdatagov.assets WHERE connection_id=%s AND external_id=%s", (connection_id, tag.asset_external_id))
                    asset_row = cursor.fetchone()
                    if not asset_row:
                        continue
                    cursor.execute("INSERT INTO fastdatagov.tags (key, label, category) VALUES (%s,%s,'platform') ON CONFLICT (key) DO UPDATE SET label=excluded.label RETURNING id", (tag.key, tag.key))
                    tag_id = cursor.fetchone()[0]
                    cursor.execute("INSERT INTO fastdatagov.asset_tags (asset_id, tag_id, source, tag_value) VALUES (%s,%s,%s,%s) ON CONFLICT (asset_id, tag_id) DO UPDATE SET source=excluded.source,tag_value=excluded.tag_value", (asset_row[0], tag_id, tag.source,tag.value))
                    counts["tags"] += 1
                cursor.execute("DELETE FROM fastdatagov.asset_visibility av USING fastdatagov.assets a WHERE a.id=av.asset_id AND a.connection_id=%s AND av.source<>'fastdatagov'",(connection_id,))
                for grant in adapter.discover_grants(governed_external_ids):
                    cursor.execute("SELECT id FROM fastdatagov.assets WHERE connection_id=%s AND external_id=%s", (connection_id, grant.asset_external_id))
                    asset_row = cursor.fetchone()
                    if not asset_row:
                        continue
                    cursor.execute("INSERT INTO fastdatagov.asset_visibility (asset_id,principal_type,principal_key,privilege,source) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (asset_id,principal_type,principal_key,privilege) DO UPDATE SET source=excluded.source", (asset_row[0], grant.principal_type, grant.principal_key, grant.privilege, grant.source))
                    counts["grants"] += 1
                connection.commit()

            lineage_page = _collect_pages(adapter.discover_lineage,sync_cursor.get("lineage"))
            usage_page = _collect_pages(adapter.discover_usage,sync_cursor.get("usage"))
            with connect() as connection, connection.cursor() as cursor:
                for edge in lineage_page.records:
                    cursor.execute("SELECT id FROM fastdatagov.assets WHERE connection_id=%s AND external_id=%s", (connection_id, edge.source_external_id)); source = cursor.fetchone()
                    cursor.execute("SELECT id FROM fastdatagov.assets WHERE connection_id=%s AND external_id=%s", (connection_id, edge.target_external_id)); target = cursor.fetchone()
                    if not source or not target:
                        continue
                    source_field_id=target_field_id=None
                    if edge.source_field:
                        cursor.execute("SELECT id FROM fastdatagov.asset_fields WHERE asset_id=%s AND lower(name)=lower(%s)",(source[0],edge.source_field)); field=cursor.fetchone(); source_field_id=field[0] if field else None
                    if edge.target_field:
                        cursor.execute("SELECT id FROM fastdatagov.asset_fields WHERE asset_id=%s AND lower(name)=lower(%s)",(target[0],edge.target_field)); field=cursor.fetchone(); target_field_id=field[0] if field else None
                    cursor.execute(
                        """
                        INSERT INTO fastdatagov.lineage_edges
                            (source_asset_id, target_asset_id, source_field_id, target_field_id, operation, evidence_type, confidence, evidence)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (source_asset_id, target_asset_id, source_field_id, target_field_id, operation)
                        DO UPDATE SET evidence_type=excluded.evidence_type, confidence=excluded.confidence,
                                      evidence=excluded.evidence, observed_at=now()
                        """,
                        (source[0], target[0], source_field_id, target_field_id, edge.operation, edge.evidence_type, edge.confidence, Jsonb(edge.evidence)),
                    )
                    counts["lineage"] += 1
                for usage in usage_page.records:
                    cursor.execute("SELECT id FROM fastdatagov.assets WHERE connection_id=%s AND external_id=%s", (connection_id, usage.asset_external_id)); asset_row = cursor.fetchone()
                    if not asset_row:
                        continue
                    cursor.execute(
                        """
                        INSERT INTO fastdatagov.usage_rollups (asset_id, usage_date, query_count, distinct_users)
                        VALUES (%s,%s,%s,%s)
                        ON CONFLICT (asset_id, usage_date) DO UPDATE SET
                            query_count=excluded.query_count, distinct_users=excluded.distinct_users
                        """,
                        (asset_row[0], usage.period_end.date(), usage.query_count, usage.distinct_users),
                    )
                    counts["usage"] += 1
                combined_cursor = {"assets": asset_page.next_cursor, "lineage": lineage_page.next_cursor, "usage": usage_page.next_cursor}
                cursor.execute("UPDATE fastdatagov.connections SET sync_cursor=%s, status='healthy', last_sync_at=now(), last_error=NULL, updated_at=now() WHERE id=%s", (Jsonb(combined_cursor), connection_id))
                cursor.execute("UPDATE fastdatagov.sync_runs SET status='succeeded', cursor_after=%s, assets_seen=%s, fields_seen=%s, lineage_edges_seen=%s, completed_at=now() WHERE id=%s", (Jsonb(combined_cursor), counts["assets"], counts["fields"], counts["lineage"], sync_run_id))
                cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject, action, entity_type, entity_key, after_data) VALUES (%s,'adapter.sync_completed','connection',%s,%s)", (f"adapter:{adapter.key}", str(connection_id), Jsonb(counts)))
                connection.commit()
        return counts
    except Exception as exc:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE fastdatagov.connections SET status='error', last_error=%s, updated_at=now() WHERE id=%s", (str(exc)[:2000], connection_id))
            cursor.execute("UPDATE fastdatagov.sync_runs SET status='failed', error_summary=%s, completed_at=now() WHERE id=%s", (str(exc)[:2000], sync_run_id))
            connection.commit()
        raise


def run_quality(rule_id: int) -> dict:
    row = fetch_one(
        """
        SELECT qr.*, a.external_id, a.connection_id, a.steward_email
        FROM fastdatagov.quality_rules qr
        JOIN fastdatagov.assets a ON a.id=qr.asset_id
        WHERE qr.id=%s AND qr.enabled=true
        """,
        (rule_id,),
    )
    if not row:
        raise ValueError(f"Enabled quality rule {rule_id} does not exist")
    adapter = _adapter_for_connection(row["connection_id"])
    spec = QualityRuleSpec(row["external_id"], row["rule_type"], row["expression"], float(row.get("threshold") or 100), settings().quality_statement_timeout_seconds)
    with adapter:
        if row["rule_type"]=="custom_python":
            from fastdatagov.quality_plugins import execute as execute_python_quality
            result=execute_python_quality(adapter,spec)
        else:
            result = adapter.execute_quality(spec)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("INSERT INTO fastdatagov.quality_runs (rule_id, status, score, observed_value, rows_evaluated, message, completed_at, evidence) VALUES (%s,%s,%s,%s,%s,%s,now(),%s)", (rule_id, result.status, result.score, result.observed_value, result.rows_evaluated, result.message, Jsonb(result.evidence)))
        cursor.execute("""UPDATE fastdatagov.assets SET quality_score=(SELECT avg(latest.score) FROM fastdatagov.quality_rules qr2 JOIN LATERAL (SELECT score FROM fastdatagov.quality_runs qrun WHERE qrun.rule_id=qr2.id AND qrun.completed_at IS NOT NULL ORDER BY qrun.started_at DESC LIMIT 1) latest ON true WHERE qr2.asset_id=%s), updated_at=now() WHERE id=%s""", (row["asset_id"], row["asset_id"]))
        cursor.execute("""UPDATE fastdatagov.assets SET trust_score=least(100,coalesce(quality_score,0)*0.55+CASE certification_status WHEN 'certified' THEN 15 WHEN 'verified' THEN 10 ELSE 0 END+CASE WHEN owner_email IS NOT NULL AND owner_email<>'' THEN 10 ELSE 0 END+CASE WHEN steward_email IS NOT NULL AND steward_email<>'' THEN 10 ELSE 0 END+CASE WHEN business_description<>'' THEN 5 ELSE 0 END+CASE WHEN coalesce(refreshed_at,last_observed_at)>=now()-interval '7 days' THEN 5 ELSE 0 END) WHERE id=%s""",(row["asset_id"],))
        if result.status == "failed":
            assignee=row.get("owner_email") or row.get("steward_email") or settings().governance_fallback_assignee
            cursor.execute("""INSERT INTO fastdatagov.work_items (kind,asset_id,title,description,priority,assignee_email,payload)
                              SELECT 'quality',%s,%s,%s,%s,%s,%s WHERE NOT EXISTS
                              (SELECT 1 FROM fastdatagov.work_items WHERE kind='quality' AND status NOT IN ('resolved','rejected') AND payload->>'rule_id'=%s)""", (row["asset_id"], f"Resolve: {row['name']}", result.message, row["severity"], assignee, Jsonb({"rule_id": rule_id}),str(rule_id)))
            cursor.execute("""INSERT INTO fastdatagov.notification_outbox (channel_id,event_type,recipient,subject,body,payload)
                              SELECT id,'quality.failed',%s,%s,%s,%s FROM fastdatagov.notification_channels
                              WHERE enabled AND (cardinality(events)=0 OR 'quality.failed'=ANY(events))""",(assignee,f"Quality failed: {row['name']}",result.message,Jsonb({"rule_id":rule_id,"asset_id":row["asset_id"],"score":result.score})))
        cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES ('worker','quality.run_completed','quality_rule',%s,%s)",(str(rule_id),Jsonb({"status":result.status,"score":result.score,"rows_evaluated":result.rows_evaluated})))
        connection.commit()
    return {"rule_id": rule_id, "status": result.status, "score": result.score}


def check_connection_health(connection_id: int) -> dict:
    adapter=_adapter_for_connection(connection_id)
    try:
        with adapter:
            health=adapter.health()
    except Exception as exc:
        from fastdatagov.adapters.base import AdapterNotConfigured
        if isinstance(exc, AdapterNotConfigured):
            status,message,latency="ready",str(exc),None
        else:
            status,message,latency="unhealthy",str(exc),None
    else:
        status,message,latency=health.status,health.message,health.latency_ms
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("INSERT INTO fastdatagov.connection_health_checks (connection_id,status,message,latency_ms) VALUES (%s,%s,%s,%s)",(connection_id,status,message,latency))
        cursor.execute("UPDATE fastdatagov.connections SET status=%s,last_error=%s,updated_at=now() WHERE id=%s",(status,None if status in {"healthy","ready"} else message,connection_id)); connection.commit()
    return {"connection_id":connection_id,"status":status,"message":message,"latency_ms":latency}


def write_tags(connection_id: int, asset_external_id: str, tags: dict[str,str]) -> dict:
    adapter=_adapter_for_connection(connection_id)
    with adapter: adapter.write_tags(asset_external_id,tags)
    return {"connection_id":connection_id,"asset_external_id":asset_external_id,"tags":len(tags)}
