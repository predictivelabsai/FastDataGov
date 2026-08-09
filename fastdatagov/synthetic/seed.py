"""Idempotently seed the neutral demonstration corpus into PostgreSQL."""

from __future__ import annotations

import os

from psycopg.types.json import Jsonb

from fastdatagov.db import connect
from fastdatagov.db.migrate import migrate
from fastdatagov.synthetic.data import ADAPTERS, ASSETS, AUDIT, GLOSSARY, LINEAGE, QUALITY_RULES, WORK_ITEMS


def seed() -> dict[str, int]:
    migrate()
    counts = {"assets": 0, "fields": 0, "lineage": 0, "quality": 0, "work": 0}
    with connect() as connection, connection.cursor() as cursor:
        for domain in sorted({asset.domain for asset in ASSETS} | {term.domain for term in GLOSSARY}):
            cursor.execute("INSERT INTO fastdatagov.domains (key, name) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET name=excluded.name", (domain.lower().replace(" ", "-"), domain))

        platform_ids = {}
        connection_ids = {}
        for adapter in ADAPTERS:
            key = adapter.key
            cursor.execute("INSERT INTO fastdatagov.platforms (key, name, adapter_type, status) VALUES (%s,%s,%s,'ready') ON CONFLICT (key) DO UPDATE SET name=excluded.name, adapter_type=excluded.adapter_type RETURNING id", (key, key.title(), key))
            platform_ids[key] = cursor.fetchone()[0]
            config = {"demo": True}
            credential_ref = ""
            if key == "snowflake":
                config = {"account": os.getenv("SNOWFLAKE_ACCOUNT","configure-me"), "user": os.getenv("SNOWFLAKE_USER","FASTDATAGOV"), "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE","GOVERNANCE_WH"), "role": os.getenv("SNOWFLAKE_ROLE","DATA_GOVERNANCE_READER"), "quality_warehouse": os.getenv("SNOWFLAKE_QUALITY_WAREHOUSE","GOVERNANCE_QUALITY_WH"), "quality_role": os.getenv("SNOWFLAKE_QUALITY_ROLE","DATA_QUALITY_EXECUTOR"), "writeback_role": os.getenv("SNOWFLAKE_WRITEBACK_ROLE","")}
                credential_ref = "env:SNOWFLAKE_PASSWORD"
            cursor.execute("INSERT INTO fastdatagov.connections (platform_id, key, name, credential_ref, config, status, last_sync_at) VALUES (%s,%s,%s,%s,%s,%s,now()) ON CONFLICT (key) DO UPDATE SET name=excluded.name, config=excluded.config RETURNING id", (platform_ids[key], key, adapter.name, credential_ref, Jsonb(config), adapter.status))
            connection_ids[key] = cursor.fetchone()[0]

        asset_ids = {}
        for asset in ASSETS:
            key = asset.platform.lower()
            cursor.execute("SELECT id FROM fastdatagov.domains WHERE name=%s", (asset.domain,)); domain_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO fastdatagov.assets
                    (connection_id, external_id, qualified_name, name, asset_type, platform_key,
                     domain_id, description, business_description, owner_email, steward_email,
                     sensitivity, certification_status, quality_score, trust_score, access_guidance,
                     source_url, native_metadata, refreshed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
                ON CONFLICT (connection_id, external_id) DO UPDATE SET
                    qualified_name=excluded.qualified_name, name=excluded.name,
                    business_description=excluded.business_description, owner_email=excluded.owner_email,
                    steward_email=excluded.steward_email, quality_score=excluded.quality_score,
                    trust_score=excluded.trust_score, updated_at=now()
                RETURNING id
                """,
                (connection_ids[key], str(asset.id), asset.qualified_name, asset.name, asset.asset_type,
                 key, domain_id, asset.description, asset.business_description, asset.owner, asset.steward,
                 asset.sensitivity, asset.certification, asset.quality_score, asset.trust_score,
                 asset.access_guidance, asset.source_url, Jsonb({"demo_freshness": asset.freshness})),
            )
            database_id = cursor.fetchone()[0]
            asset_ids[asset.id] = database_id
            counts["assets"] += 1
            for ordinal, column in enumerate(asset.fields, 1):
                cursor.execute("INSERT INTO fastdatagov.asset_fields (asset_id, external_id, name, ordinal, data_type, nullable, description, classification) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (asset_id, external_id) DO UPDATE SET data_type=excluded.data_type, description=excluded.description, classification=excluded.classification", (database_id, f"{asset.id}:{column.name}", column.name, ordinal, column.data_type, column.nullable, column.description, column.classification))
                counts["fields"] += 1
            for tag in asset.tags:
                cursor.execute("INSERT INTO fastdatagov.tags (key,label) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET label=excluded.label RETURNING id", (tag, tag.replace("-", " ").title())); tag_id = cursor.fetchone()[0]
                cursor.execute("INSERT INTO fastdatagov.asset_tags (asset_id, tag_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (database_id, tag_id))
            cursor.execute("INSERT INTO fastdatagov.usage_rollups (asset_id, usage_date, query_count, distinct_users) VALUES (%s,current_date,%s,%s) ON CONFLICT (asset_id, usage_date) DO UPDATE SET query_count=excluded.query_count, distinct_users=excluded.distinct_users", (database_id, asset.usage_30d, max(1, asset.usage_30d // 14)))

        term_ids = {}
        for term in GLOSSARY:
            cursor.execute("SELECT id FROM fastdatagov.domains WHERE name=%s", (term.domain,)); domain_id = cursor.fetchone()[0]
            term_key = term.name.lower().replace(" ", "-")
            cursor.execute("INSERT INTO fastdatagov.glossary_terms (key,name,definition,domain_id,owner_email,status) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (key) DO UPDATE SET definition=excluded.definition, owner_email=excluded.owner_email, status=excluded.status RETURNING id", (term_key, term.name, term.definition, domain_id, term.owner, term.status)); term_ids[term.name] = cursor.fetchone()[0]
        for asset in ASSETS:
            for term_name in asset.terms:
                cursor.execute("INSERT INTO fastdatagov.asset_terms (asset_id, term_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (asset_ids[asset.id], term_ids[term_name]))

        for edge in LINEAGE:
            cursor.execute("INSERT INTO fastdatagov.lineage_edges (source_asset_id,target_asset_id,operation,evidence_type,confidence) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (asset_ids[edge.source_id], asset_ids[edge.target_id], edge.operation, edge.evidence_type, edge.confidence)); counts["lineage"] += 1

        rule_ids = {}
        for rule in QUALITY_RULES:
            cursor.execute("SELECT id FROM fastdatagov.quality_rules WHERE asset_id=%s AND name=%s", (asset_ids[rule.asset_id], rule.name)); existing = cursor.fetchone()
            if existing:
                rule_id = existing[0]
            else:
                cursor.execute("INSERT INTO fastdatagov.quality_rules (asset_id,name,rule_type,expression,threshold,severity,schedule) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id", (asset_ids[rule.asset_id], rule.name, rule.rule_type, rule.expression, 95, rule.severity, rule.schedule)); rule_id = cursor.fetchone()[0]
                cursor.execute("INSERT INTO fastdatagov.quality_runs (rule_id,status,score,observed_value,rows_evaluated,message,completed_at) VALUES (%s,%s,%s,%s,10000,%s,now())", (rule_id, "passed" if rule.status == "passed" else "failed", rule.score, 100-rule.score, "Seeded deterministic result"))
            rule_ids[rule.id] = rule_id
            counts["quality"] += 1

        for item in WORK_ITEMS:
            cursor.execute("SELECT id FROM fastdatagov.work_items WHERE title=%s", (item.title,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO fastdatagov.work_items (kind,asset_id,title,description,status,priority,assignee_email,due_at) VALUES (%s,%s,%s,%s,%s,%s,%s,current_date + 7)", (item.kind, asset_ids[item.asset_id], item.title, item.description, item.status, item.priority, item.assignee)); counts["work"] += 1

        for key,name,description,domain,owner,steward,status,service_level,guidance,members in (
            ("customer-360","Customer 360","Reusable customer insight product with quality and lineage evidence.","Customer","alex.owner@example.com","sam.steward@example.com","active","Daily by 08:00 UTC; 99.5% availability","Request CUSTOMER_ANALYTICS access.",(7,10)),
            ("revenue-reporting","Revenue reporting","Certified finance reporting assets and semantic model.","Finance","noah.owner@example.com","ivy.steward@example.com","active","Hourly refresh","Available to approved finance users.",(4,11)),
        ):
            cursor.execute("SELECT id FROM fastdatagov.domains WHERE name=%s",(domain,)); domain_id=cursor.fetchone()[0]
            cursor.execute("INSERT INTO fastdatagov.data_products (key,name,description,domain_id,owner_email,steward_email,status,service_level,access_guidance,certification_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'verified') ON CONFLICT (key) DO UPDATE SET description=excluded.description,updated_at=now() RETURNING id",(key,name,description,domain_id,owner,steward,status,service_level,guidance)); product_id=cursor.fetchone()[0]
            for member in members: cursor.execute("INSERT INTO fastdatagov.product_assets (product_id,asset_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",(product_id,asset_ids[member]))
        cursor.execute("UPDATE fastdatagov.pilot_metrics SET baseline=CASE key WHEN 'catalog_coverage' THEN 60 WHEN 'accountability_coverage' THEN 45 WHEN 'quality_rule_coverage' THEN 20 WHEN 'time_to_trusted_data' THEN 32 WHEN 'weekly_active_users' THEN 0 END WHERE baseline IS NULL")

        cursor.execute("SELECT count(*) FROM fastdatagov.audit_events")
        if cursor.fetchone()[0] == 0:
            for event in AUDIT:
                cursor.execute("INSERT INTO fastdatagov.audit_events (actor_subject,action,entity_type,entity_key,after_data) VALUES (%s,%s,'demo',%s,%s)", (event.actor, event.action.replace(" ", "_"), event.entity, Jsonb({"detail": event.detail})))
        connection.commit()
    return counts


def main() -> None:
    result = seed()
    print("Seeded " + ", ".join(f"{key}={value}" for key, value in result.items()))


if __name__ == "__main__":
    main()
