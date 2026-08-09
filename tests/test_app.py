from __future__ import annotations


def test_landing_is_generic_and_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Know which data to trust" in response.text
    assert "Open-source data governance" in response.text
    assert "Sign in" in response.text
    assert 'href="/features"' in response.text
    assert 'href="/compare"' in response.text
    assert "OpenMetadata" in response.text


def test_public_feature_catalog_explains_adapter_availability(client):
    response = client.get("/features")
    assert response.status_code == 200
    assert "Unified data catalog" in response.text
    assert "Snowflake adapter" in response.text
    assert "Pilot-ready" in response.text
    assert "Contract-ready" in response.text
    assert "Free · MIT" in response.text


def test_public_comparison_is_source_linked_and_candid(client):
    response = client.get("/compare")
    assert response.status_code == 200
    for platform in ("FastDataGov", "OpenMetadata", "DataHub", "Atlan", "Collibra", "Alation"):
        assert platform in response.text
    assert "9 August 2026" in response.text
    assert "official product documentation" in response.text
    assert "Fabric and Databricks transports are contract-ready" in response.text
    assert 'rel="canonical"' in response.text
    assert 'href="http://localhost:5062/compare"' in response.text


def test_health_and_readiness_are_public(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json() == {"status": "ready", "repository": "demo"}


def test_workspace_requires_authentication(client):
    response = client.get("/app", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/auth/login")


def test_developer_auth_rejects_invalid_email(client):
    response = client.post("/auth/dev", data={"email": "invalid", "next_path": "/app"})
    assert response.status_code == 200
    assert "valid email" in response.text


def test_google_auth_has_safe_unconfigured_fallback(client):
    response = client.get("/auth/google")
    assert response.status_code == 200
    assert "Google authentication is not configured" in response.text


def test_dashboard_renders_all_primary_navigation(authenticated_client):
    response = authenticated_client.get("/app")
    assert response.status_code == 200
    for label in ("Catalog", "Lineage", "Data quality", "Stewardship", "Glossary", "Administration"):
        assert label in response.text
    assert "Catalog coverage" in response.text


def test_catalog_filters_search_and_platform(authenticated_client):
    response = authenticated_client.get("/app/catalog", params={"q": "revenue", "platform": "Snowflake"})
    assert response.status_code == 200
    assert "Daily revenue" in response.text
    assert "Customer feature table" not in response.text


def test_asset_page_has_accountability_fields_and_workflows(authenticated_client):
    response = authenticated_client.get("/app/assets/1")
    assert response.status_code == 200
    assert "Customer identifier is complete" in response.text
    assert "CUSTOMER_ID" in response.text
    assert "Request access" in response.text
    assert "Attest ownership" in response.text


def test_lineage_page_contains_evidence_and_graph_data(authenticated_client):
    response = authenticated_client.get("/app/lineage", params={"asset_id": 7})
    assert response.status_code == 200
    assert "Evidence guide" in response.text
    assert "lineage-edge-data" in response.text
    assert "Customer 360" in response.text


def test_all_five_workflow_types_are_visible(authenticated_client):
    response = authenticated_client.get("/app/work")
    assert response.status_code == 200
    for kind in ("Quality", "Certification", "Metadata", "Access", "Attestation"):
        assert kind in response.text


def test_create_and_transition_workflow(authenticated_client):
    created = authenticated_client.post(
        "/app/work/create",
        data={"kind": "access", "asset_id": "2"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    queue = authenticated_client.get(created.headers["location"])
    assert "Access request for Sales order" in queue.text

    transitioned = authenticated_client.post(
        "/app/work/1/status",
        data={"status": "in_progress"},
        headers={"HX-Request": "true"},
    )
    assert transitioned.status_code == 200
    assert "In Progress" in transitioned.text


def test_api_requires_authentication(client):
    response = client.get("/api/v1/assets")
    assert response.status_code == 401
    assert response.json()["error"] == "authentication_required"


def test_api_catalog_and_lineage(authenticated_client):
    assets = authenticated_client.get("/api/v1/assets", params={"platform": "Fabric"})
    assert assets.status_code == 200
    assert assets.json()["meta"]["count"] == 3
    assert all(asset["platform"] == "Fabric" for asset in assets.json()["data"])

    lineage = authenticated_client.get("/api/v1/lineage", params={"asset_id": 7})
    assert lineage.status_code == 200
    assert lineage.json()["meta"]["count"] >= 2


def test_static_assets_are_served(client):
    stylesheet = client.get("/styles.css")
    script = client.get("/app.js")
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "--accent" in stylesheet.text


def test_project_files_are_not_exposed_as_static_assets(client):
    for path in ("/requirements.txt", "/pyproject.toml", "/README.md", "/.env"):
        assert client.get(path).status_code == 404


def test_security_headers_and_cross_site_post_protection(client):
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    rejected = client.post(
        "/auth/dev",
        data={"email": "governance@example.com"},
        headers={"Origin": "https://attacker.example"},
    )
    assert rejected.status_code == 403


def test_complete_governance_authoring_pages_render(authenticated_client):
    for path, marker in (
        ("/app/products", "Governed data products"), ("/app/products/new", "Describe a reusable data product"),
        ("/app/assets/1/edit", "Improve business context"), ("/app/glossary/new", "Define a governed term"),
        ("/app/lineage/manage", "Fill evidence gaps safely"), ("/app/quality/new", "Define a measurable expectation"),
        ("/app/work/1", "Discussion"), ("/app/admin/domains", "Governance operating controls"),
        ("/app/admin/jobs", "adapter.sync"), ("/app/admin/pilot", "Time to trusted data"),
    ):
        response = authenticated_client.get(path)
        assert response.status_code == 200
        assert marker in response.text


def test_business_authoring_mutations_are_functional(authenticated_client):
    product = authenticated_client.post("/app/products/save", data={"name":"Service metrics","description":"Reusable service data","domain":"Customer","owner":"owner@example.com","steward":"steward@example.com","status":"active","service_level":"Hourly","access_guidance":"Request access","asset_ids":["6","7"]}, follow_redirects=False)
    assert product.status_code == 303
    assert "Service metrics" in authenticated_client.get("/app/products").text
    metadata = authenticated_client.post("/app/assets/6/metadata", data={"business_description":"Approved service context","owner":"owner@example.com","steward":"steward@example.com","sensitivity":"restricted","access_guidance":"Privacy approval","tags":"governed, service","term_ids":["1","8"]}, follow_redirects=False)
    assert metadata.status_code == 303
    assert "Approved service context" in authenticated_client.get("/app/assets/6").text
    term = authenticated_client.post("/app/glossary/save", data={"name":"Resolution","definition":"A completed service outcome.","domain":"Customer","owner":"owner@example.com","status":"approved"}, follow_redirects=False)
    assert term.status_code == 303
    assert "Resolution" in authenticated_client.get("/app/glossary").text


def test_machine_api_includes_products_work_audit_and_csv_export(authenticated_client):
    for path in ("/api/v1/products","/api/v1/work","/api/v1/domains","/api/v1/audit","/api/v1/jobs","/api/v1/pilot-metrics"):
        response=authenticated_client.get(path)
        assert response.status_code==200 and "data" in response.json()
    export=authenticated_client.get("/api/v1/exports/assets")
    assert export.status_code==200 and export.headers["content-type"].startswith("text/csv")
    assert "qualified_name" in export.text


def test_json_api_can_create_lineage_quality_and_comments(authenticated_client):
    edge=authenticated_client.post("/api/v1/lineage",json={"source_id":6,"target_id":10,"operation":"feature derivation","confidence":.8})
    assert edge.status_code==200 and edge.json()["data"]["evidence_type"]=="manual"
    rule=authenticated_client.post("/api/v1/quality",json={"asset_id":6,"name":"Resolution present","rule_type":"completeness","expression":"RESOLUTION IS NOT NULL","threshold":95,"severity":"high","schedule":"daily"})
    assert rule.status_code==200
    run=authenticated_client.post(f"/api/v1/quality/{rule.json()['data']['id']}/runs")
    assert run.json()["data"]["status"]=="queued"
    comment=authenticated_client.post("/api/v1/work/1/comments",json={"body":"Investigating upstream records."})
    assert comment.status_code==200 and comment.json()["data"]["body"].startswith("Investigating")


def test_operations_configuration_and_accountability_mutations(authenticated_client):
    assert authenticated_client.post("/app/admin/connections/save",data={"key":"demo-local","name":"Demo local","adapter_type":"demo","credential_ref":"","config_json":"{\"demo\":true}"},follow_redirects=False).status_code==303
    assert authenticated_client.post("/app/admin/connections/demo-local/job",data={"kind":"adapter.health"},follow_redirects=False).status_code==303
    assert authenticated_client.post("/app/admin/workflows/quality/save",data={"due_days":"4","approval_role":"owner","enabled":"true"},follow_redirects=False).status_code==303
    assert authenticated_client.post("/app/admin/notifications/save",data={"key":"teams-governance","channel_type":"teams","endpoint_ref":"env:TEAMS_GOVERNANCE_WEBHOOK","events":"workflow.created, quality.failed","enabled":"true"},follow_redirects=False).status_code==303
    assert authenticated_client.post("/app/admin/aliases/save",data={"identity_principal_type":"group","identity_key":"entra-group-id","platform_key":"snowflake","source_principal_key":"ANALYST_ROLE"},follow_redirects=False).status_code==303
    assert authenticated_client.post("/app/admin/accountability/save",data={"scope_type":"product","scope_id":"1","responsibility":"owner","email":"owner@example.com","expires_days":"365"},follow_redirects=False).status_code==303
    assert "teams-governance" in authenticated_client.get("/app/admin/notifications").text
    assert "ANALYST_ROLE" in authenticated_client.get("/app/admin/access").text


def test_lineage_quality_certification_and_discussion_mutations(authenticated_client):
    created=authenticated_client.post("/app/lineage/create",data={"source_id":"6","target_id":"10","operation":"feature derivation","confidence":"0.8"},follow_redirects=False)
    assert created.status_code==303 and "feature derivation" in authenticated_client.get("/app/lineage/manage").text
    assert authenticated_client.post("/app/quality/save",data={"asset_id":"6","name":"Body present","rule_type":"completeness","expression":"BODY IS NOT NULL","threshold":"95","severity":"high","schedule":"daily"},follow_redirects=False).status_code==303
    assert authenticated_client.post("/app/assets/6/certify",data={"status":"verified","expires_days":"365","notes":"Reviewed"},follow_redirects=False).status_code==303
    assert authenticated_client.post("/app/products/1/certify",data={"status":"certified","expires_days":"365","notes":"Reviewed"},follow_redirects=False).status_code==303
    assert authenticated_client.post("/app/work/1/comments",data={"body":"Decision context"},follow_redirects=False).status_code==303
    assert "Decision context" in authenticated_client.get("/app/work/1").text


def test_read_only_routes_reject_post(authenticated_client):
    for path in ("/app/catalog","/app/products","/app/lineage","/api/v1/assets","/api/v1/products","/healthz"):
        assert authenticated_client.post(path).status_code==405


def test_lineage_impact_api_is_directional_and_bounded(authenticated_client):
    response=authenticated_client.get("/api/v1/lineage/impact",params={"asset_id":1,"direction":"downstream","depth":3})
    assert response.status_code==200
    assert response.json()["data"]["root_asset_id"]==1
    assert 7 in response.json()["data"]["affected_asset_ids"]
