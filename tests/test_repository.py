from __future__ import annotations

from fastdatagov.models import UserIdentity
from fastdatagov.repository import DemoRepository


IDENTITY = UserIdentity("test", "lead@example.com", "Governance Lead", ("governance_lead",))


def test_demo_metrics_are_internally_consistent():
    repo = DemoRepository()
    metrics = repo.metrics(IDENTITY)
    assert metrics["assets"] == len(repo.list_assets(identity=IDENTITY))
    assert metrics["platforms"] == 3
    assert 0 <= metrics["quality_score"] <= 100
    assert metrics["accountability_pct"] == 100


def test_quality_rules_have_separate_run_time_expression_and_trend():
    rules = DemoRepository().quality_rules()
    assert all(isinstance(rule.last_run, str) and "ago" in rule.last_run for rule in rules)
    assert all(isinstance(rule.expression, str) and rule.expression for rule in rules)
    assert all(rule.trend for rule in rules)


def test_search_indexes_business_and_technical_context():
    repo = DemoRepository()
    assert {asset.name for asset in repo.list_assets("customer-360")} == {"Customer 360", "Customer"}
    assert any(asset.name == "Daily revenue" for asset in repo.list_assets("Net revenue"))
    assert repo.list_assets("PROD.FINANCE.INVOICE")[0].name == "Invoice"


def test_filters_can_combine():
    repo = DemoRepository()
    results = repo.list_assets(platform="Snowflake", domain="Finance", trust="certified")
    assert {asset.name for asset in results} == {"Invoice", "Daily revenue"}


def test_workflow_creation_and_audit_are_atomic_in_demo_repository():
    repo = DemoRepository()
    before_work = len(repo.work_items())
    before_audit = len(repo.audit())
    item = repo.create_work_item("metadata", 1, IDENTITY)
    assert len(repo.work_items()) == before_work + 1
    assert len(repo.audit()) == before_audit + 1
    assert item.assignee == repo.get_asset(1).steward
    updated = repo.update_work_item(item.id, "in_progress", IDENTITY)
    assert updated.status == "in_progress"


def test_invalid_workflow_kind_and_status_are_rejected():
    repo = DemoRepository()
    for operation in (
        lambda: repo.create_work_item("delete", 1, IDENTITY),
        lambda: repo.update_work_item(1, "deleted", IDENTITY),
    ):
        try:
            operation()
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError")


def test_governance_authoring_covers_products_metadata_glossary_lineage_and_quality():
    repo = DemoRepository()
    identity = UserIdentity("test", "steward@example.com", "Steward", ("steward", "engineer", "owner"))
    product = repo.save_product(identity, "Service health", "Reusable service metrics", "Customer", identity.email, identity.email, "active", "Hourly", "Approved analysts", [6, 7])
    assert product.asset_ids == [6, 7]
    updated = repo.update_asset_metadata(6, identity, "Governed support context", identity.email, identity.email, "restricted", "Privacy approval", ["service", "governed"], [1, 8])
    assert updated.terms == ["Customer", "Support case"]
    assert repo.save_term(identity, "Resolution", "A completed service outcome.", "Customer", identity.email, "approved").status == "approved"
    edge = repo.save_lineage(identity, 6, 10, "feature derivation", .8)
    assert edge.evidence_type == "manual"
    repo.delete_lineage(edge.id, identity)
    rule = repo.save_quality_rule(identity, 6, "Resolution is present", "completeness", "RESOLUTION IS NOT NULL", 95, "high", "daily")
    assert repo.queue_quality_run(rule.id, identity) > 0


def test_accountability_certification_comments_roles_and_pilot_evidence():
    repo = DemoRepository()
    identity = UserIdentity("test", "owner@example.com", "Owner", ("owner", "admin"))
    assert repo.assign_accountability(identity, "asset", 1, "owner", identity.email).responsibility == "owner"
    repo.certify_asset(1, identity, "certified", 365, "Evidence reviewed")
    assert repo.get_asset(1).certification == "certified"
    comment = repo.add_work_comment(1, identity, "Investigating upstream records.")
    assert repo.work_comments(1) == [comment]
    assert repo.save_role(identity, "group", "finance-readers", "consumer") in repo.roles()
    assert {metric.key for metric in repo.pilot_metrics()} == {"catalog_coverage", "accountability_coverage", "quality_rule_coverage", "time_to_trusted_data", "weekly_active_users"}


def test_operations_configuration_and_source_principal_aliases():
    repo=DemoRepository(); identity=UserIdentity("admin","admin@example.com","Admin",("admin",))
    assert repo.save_workflow_definition(identity,"quality",4,"owner",True)["due_days"]==4
    channel=repo.save_notification_channel(identity,"governance","teams","env:GOVERNANCE_WEBHOOK",["quality.failed"])
    assert channel["endpoint_ref"].startswith("env:")
    connection=repo.save_connection(identity,"demo-local","Demo local","demo","",{"demo":True})
    assert repo.queue_adapter_job(identity,connection["key"],"adapter.health")>0
    alias=repo.save_principal_alias(identity,"group","entra-id","snowflake","ANALYST_ROLE")
    assert alias in repo.principal_aliases()


def test_field_enrichment_quality_disable_and_product_certification():
    repo=DemoRepository(); identity=UserIdentity("lead","lead@example.com","Lead",("governance_lead","steward","owner"))
    field=repo.update_field_metadata(1,"CUSTOMER_ID",identity,"Stable business identifier","identifier")
    assert field.business_description=="Stable business identifier"
    repo.set_quality_enabled(1,identity,False)
    assert next(rule for rule in repo.quality_rules() if rule.id==1).enabled is False
    repo.certify_product(1,identity,"certified",365,"Evidence complete")
    assert next(product for product in repo.products(identity) if product.id==1).certification=="certified"
