from __future__ import annotations

from collections import Counter
from urllib.parse import urlencode

from fasthtml.common import *

from fastdatagov.models import Asset, QualityRule, UserIdentity, WorkItem
from fastdatagov.repository import GovernanceRepository
from fastdatagov.web.components import (
    app_shell,
    asset_row,
    empty_state,
    icon,
    metric_card,
    page_intro,
    platform_badge,
    score_ring,
    section_header,
    status_badge,
    tag_list,
)


def dashboard_page(identity: UserIdentity, repo: GovernanceRepository):
    metrics = repo.metrics(identity)
    assets = repo.list_assets(identity=identity)
    work = repo.work_items(identity=identity)
    adapters = repo.adapters(identity)
    audits = repo.audit(6, identity)
    attention = sorted(assets, key=lambda asset: asset.trust_score)[:3]
    return app_shell(
        identity,
        "Overview",
        "/app",
        page_intro("Governance overview", f"Good morning, {identity.name.split()[0]}", "A live view of coverage, trust, accountability, and the work needed to keep data reusable.", A("Browse catalog", href="/app/catalog", cls="button button-primary")),
        Div(
            metric_card("Catalog coverage", f"{metrics['catalog_coverage']}%", f"{metrics['assets']} governed assets across {metrics['platforms']} platforms", "blue"),
            metric_card("Quality score", metrics["quality_score"], "Weighted result across active quality rules", "green"),
            metric_card("Accountability", f"{metrics['accountability_pct']}%", "Assets with an owner and a steward", "violet"),
            metric_card("Open work", metrics["open_work"], "Across quality, access, metadata and approvals", "amber"),
            cls="metric-grid",
        ),
        Div(
            Section(
                section_header("Trust portfolio", "Highest-use governed assets", A("View all", href="/app/catalog", cls="inline-link")),
                Div(*[
                    A(
                        Div(platform_badge(asset.platform), status_badge(asset.certification), cls="trust-row-head"),
                        Div(Div(Strong(asset.name), Code(asset.qualified_name)), score_ring(asset.trust_score, "small"), cls="trust-row-body"),
                        Div(Span(asset.domain), Span(f"{asset.usage_30d:,} queries · 30 days"), cls="trust-row-foot"),
                        href=f"/app/assets/{asset.id}", cls="trust-row",
                    ) for asset in assets[:4]], cls="trust-list"),
                cls="panel",
            ),
            Section(
                section_header("Needs attention", "Lowest current trust signals", A("Quality dashboard", href="/app/quality", cls="inline-link")),
                Div(*[
                    A(Div(Span(asset.name[:1], cls="asset-avatar"), Div(Strong(asset.name), Small(asset.domain))), Div(Strong(f"{asset.quality_score:.1f}%"), Small("quality")), href=f"/app/assets/{asset.id}", cls="attention-row")
                    for asset in attention], cls="attention-list"),
                Div(Div(Span("Open work"), Strong(str(metrics["open_work"]))), Div(Span("Certified"), Strong(f"{metrics['certified_pct']}%")), cls="summary-pair"),
                cls="panel",
            ),
            cls="dashboard-grid",
        ),
        Div(
            Section(
                section_header("My stewardship queue", "The next decisions and fixes", A("Open queue", href="/app/work", cls="inline-link")),
                Div(*[work_item_row(item, repo) for item in work[:4]], cls="work-list"),
                cls="panel",
            ),
            Section(
                section_header("Connections", "Adapter freshness and readiness", A("Manage", href="/app/admin/adapters", cls="inline-link")),
                Div(*[Div(Div(Span(adapter.key[:1].upper(), cls=f"platform-icon {adapter.key}"), Div(Strong(adapter.name), Small(adapter.last_sync))), Div(status_badge(adapter.status), Small(f"{adapter.assets} assets")), cls="adapter-row") for adapter in adapters], cls="adapter-list"),
                cls="panel",
            ),
            cls="dashboard-grid",
        ),
        Section(
            section_header("Recent governance activity", "Evidence of changes, decisions, and platform observations"),
            Div(*[Div(Span(event.actor[:1].upper(), cls="audit-avatar"), Div(P(Strong(event.actor), f" {event.action} ", Strong(event.entity)), Small(event.detail)), Time(event.occurred_at), cls="audit-row") for event in audits], cls="audit-list"),
            cls="panel",
        ),
    )


def catalog_page(identity: UserIdentity, repo: GovernanceRepository, query: str = "", platform: str = "", domain: str = "", trust: str = "", owner: str = "", sensitivity: str = "", refreshed: str = "", page: int = 1):
    page=max(1,page); page_size=50
    page_rows = repo.list_assets(query, platform, domain, trust, identity, owner, sensitivity, refreshed,page_size+1,(page-1)*page_size)
    has_next=len(page_rows)>page_size; assets=page_rows[:page_size]
    facets=repo.catalog_facets(identity)
    platforms=facets["platforms"]; domains=facets["domains"]
    filters_active = sum(bool(value) for value in (query, platform, domain, trust, owner, sensitivity, refreshed))
    table = Table(
        Thead(Tr(Th("Asset"), Th("Platform"), Th("Domain"), Th("Trust"), Th("Quality"), Th("Accountability"), Th(""))),
        Tbody(*[asset_row(asset) for asset in assets]), cls="data-table",
    ) if assets else empty_state("No governed assets found", "Try a broader term or clear one of the filters.")
    return app_shell(
        identity, "Catalog", "/app/catalog",
        page_intro("Discovery", "Find data you can explain and reuse", "Search technical names, business definitions, glossary terms, classifications, and trust signals."),
        Form(
            Div(icon("search"), Input(name="q", value=query, placeholder="Search assets, terms, descriptions or tags", aria_label="Search catalog", autofocus=True), cls="catalog-search"),
            Div(
                Select(Option("All platforms", value=""), *[Option(value, value=value, selected=(value == platform)) for value in platforms], name="platform", aria_label="Platform"),
                Select(Option("All domains", value=""), *[Option(value, value=value, selected=(value == domain)) for value in domains], name="domain", aria_label="Domain"),
                Select(Option("All trust states", value=""), Option("Certified", value="certified", selected=(trust == "certified")), Option("Needs attention", value="attention", selected=(trust == "attention")), name="trust", aria_label="Trust state"),
                Select(Option("All sensitivities",value=""),*[Option(v.title(),value=v,selected=sensitivity==v) for v in ("public","internal","confidential","restricted")],name="sensitivity",aria_label="Sensitivity"),
                Select(Option("Any refresh time",value=""),Option("Last 24 hours",value="24h",selected=refreshed=="24h"),Option("Last 7 days",value="7d",selected=refreshed=="7d"),Option("Last 30 days",value="30d",selected=refreshed=="30d"),name="refreshed",aria_label="Last refreshed"),
                Input(name="owner",value=owner,placeholder="Owner email",aria_label="Owner"),
                Button("Apply filters", type="submit", cls="button button-primary compact"),
                A("Clear", href="/app/catalog", cls="button button-quiet compact") if filters_active else "",
                cls="filter-row",
            ),
            method="get", action="/app/catalog", cls="catalog-controls",
        ),
        Div(Div(Strong(str(len(assets))), Span(f"assets on page {page}")), Div(*[Span(f"{key}: {value}", cls="active-filter") for key, value in (("Platform", platform), ("Domain", domain), ("Trust", trust),("Sensitivity",sensitivity),("Refreshed",refreshed),("Owner",owner)) if value]), cls="result-summary"),
        Div(table, cls="table-panel"),
        Div(A("← Previous",href="/app/catalog?"+urlencode({k:v for k,v in {"q":query,"platform":platform,"domain":domain,"trust":trust,"owner":owner,"sensitivity":sensitivity,"refreshed":refreshed,"page":page-1}.items() if v}),cls="button button-quiet compact") if page>1 else "",A("Next →",href="/app/catalog?"+urlencode({k:v for k,v in {"q":query,"platform":platform,"domain":domain,"trust":trust,"owner":owner,"sensitivity":sensitivity,"refreshed":refreshed,"page":page+1}.items() if v}),cls="button button-outline compact") if has_next else "",cls="pagination"),
        wide=True,
    )


def asset_detail_page(identity: UserIdentity, repo: GovernanceRepository, asset: Asset):
    rules = [rule for rule in repo.quality_rules(identity) if rule.asset_id == asset.id]
    edges = repo.lineage(asset.id, identity)
    assets_by_id = {candidate.id: candidate for candidate in repo.list_assets(identity=identity)}
    upstream = [assets_by_id[edge.source_id] for edge in edges if edge.target_id == asset.id and edge.source_id in assets_by_id]
    downstream = [assets_by_id[edge.target_id] for edge in edges if edge.source_id == asset.id and edge.target_id in assets_by_id]
    return app_shell(
        identity, asset.name, "/app/catalog",
        Div(A("Catalog", href="/app/catalog"), Span("/"), Span(asset.name), cls="breadcrumbs"),
        Div(
            Div(Div(platform_badge(asset.platform), status_badge(asset.certification), cls="asset-title-badges"), H2(asset.name), Code(asset.qualified_name), P(asset.business_description or asset.description), tag_list(asset.tags), cls="asset-hero-copy"),
            Div(score_ring(asset.trust_score), Div(Span("Trust score"), Small("Quality, certification, ownership and freshness")), A("Edit metadata", href=f"/app/assets/{asset.id}/edit", cls="button button-outline compact") if identity.can("steward", "owner") else "", cls="asset-score"),
            cls="asset-hero",
        ),
        Div(
            Div(Span("Owner", cls="detail-label"), Strong(asset.owner), Small("Accountable for permitted use and certification"), cls="detail-card"),
            Div(Span("Steward", cls="detail-label"), Strong(asset.steward), Small("Maintains metadata and resolves quality issues"), cls="detail-card"),
            Div(Span("Sensitivity", cls="detail-label"), Strong(asset.sensitivity.title()), Small("Visibility follows imported source grants"), cls="detail-card"),
            Div(Span("Freshness", cls="detail-label"), Strong(asset.freshness), Small(f"{asset.usage_30d:,} queries in the last 30 days"), cls="detail-card"),
            cls="detail-grid",
        ),
        Div(Span("Trust evidence",cls="detail-label"),Span(f"Certification recorded: {asset.certified_at or 'Not yet'}"),Span(f"Certification expiry: {asset.certification_expires or 'Not set'}"),Span(f"Owner attested: {asset.owner_attested_at or 'Not yet'}"),cls="evidence-note"),
        Details(Summary("Technical source metadata"),Dl(*[item for key,value in sorted(asset.native_metadata.items()) for item in (Dt(str(key).replace('_',' ').title()),Dd(str(value)))],cls="definition-list") if asset.native_metadata else P("No additional native attributes were supplied by this adapter."),cls="panel source-metadata"),
        Div(
            Section(
                section_header("Business context", "Meaning, use, and access"),
                Dl(Dt("Description"), Dd(asset.description), Dt("Glossary"), Dd(tag_list(asset.terms)), Dt("Access guidance"), Dd(asset.access_guidance), cls="definition-list"),
                Div(*[Form(Input(type="hidden", name="kind", value=kind), Input(type="hidden", name="asset_id", value=str(asset.id)), Button(label, type="submit", cls="button button-outline compact"), method="post", action="/app/work/create") for kind, label in (("access", "Request access"), ("metadata", "Improve metadata"), ("certification", "Request certification"), ("attestation", "Attest ownership"))], cls="asset-actions"),
                Form(Select(*[Option(value.title(), value=value) for value in ("certified","verified","rejected")], name="status"), Input(type="number", name="expires_days", value="365", min="1", max="1825", aria_label="Certification duration in days"), Input(name="notes", placeholder="Decision notes"), Button("Record certification", type="submit", cls="button button-primary compact"), method="post", action=f"/app/assets/{asset.id}/certify", cls="inline-form") if identity.can("owner", "governance_lead") else "",
                cls="panel",
            ),
            Section(
                section_header("Quality", "Latest active rule results", A("View dashboard", href="/app/quality", cls="inline-link")),
                Div(*[Div(Div(status_badge(rule.status), Strong(rule.name), Small(rule.rule_type.title())), Div(Strong(f"{rule.score:.1f}%"), Small(rule.last_run)), cls="quality-compact-row") for rule in rules], cls="quality-compact") if rules else empty_state("No quality rules", "Add a rule to make this trust signal measurable."),
                cls="panel",
            ),
            cls="dashboard-grid",
        ),
        Section(
            section_header("Fields", f"{len(asset.fields)} documented fields"),
            Table(Thead(Tr(Th("Field"), Th("Type"), Th("Definition"), Th("Classification"), Th("Nullable"),Th("Steward action"))), Tbody(*[Tr(Td(Code(field.name)), Td(field.data_type), Td(field.business_description or field.description or "Not documented"), Td(status_badge(field.classification or "unclassified")), Td("Yes" if field.nullable else "No"),Td(Details(Summary("Enrich"),Form(Input(type="hidden",name="field_name",value=field.name),Input(name="business_description",value=field.business_description or field.description,placeholder="Business definition"),Input(name="classification",value=field.classification,placeholder="Classification"),Button("Save",type="submit",cls="button button-primary compact"),method="post",action=f"/app/assets/{asset.id}/fields",cls="mini-form"))) if identity.can("steward") else "") for field in asset.fields]), cls="data-table fields-table") if asset.fields else empty_state("No fields available", "This asset type does not expose column-level metadata."),
            cls="panel",
        ),
        Section(
            section_header("Lineage and impact", "Evidence-backed upstream inputs and downstream consumers", A("Open graph", href=f"/app/lineage?asset_id={asset.id}", cls="inline-link")),
            Div(lineage_neighbour_group("Upstream", upstream), Div(Span("Current asset", cls="lineage-column-label"), A(Strong(asset.name), Small(asset.platform), href=f"/app/assets/{asset.id}", cls="lineage-mini-node current"), cls="lineage-neighbour-column"), lineage_neighbour_group("Downstream", downstream), cls="lineage-neighbours"),
            cls="panel",
        ),
    )


def lineage_neighbour_group(label: str, assets: list[Asset]):
    return Div(Span(label, cls="lineage-column-label"), *[A(Strong(asset.name), Small(asset.platform), href=f"/app/assets/{asset.id}", cls="lineage-mini-node") for asset in assets], cls="lineage-neighbour-column")


def lineage_page(identity: UserIdentity, repo: GovernanceRepository, asset_id: int | None = None, evidence: str = "", direction: str = "both", depth: int = 1):
    assets = repo.list_assets(identity=identity)
    all_edges = repo.lineage(None, identity)
    if asset_id:
        frontier={asset_id}; reached={asset_id}; edges=[]
        for _ in range(max(1,min(depth,5))):
            selected=[edge for edge in all_edges if (direction in {"both","upstream"} and edge.target_id in frontier) or (direction in {"both","downstream"} and edge.source_id in frontier)]
            edges.extend(edge for edge in selected if edge not in edges)
            frontier=({edge.source_id for edge in selected}|{edge.target_id for edge in selected})-reached; reached|=frontier
    else: edges=all_edges
    if evidence:
        edges = [edge for edge in edges if edge.evidence_type == evidence]
    visible_ids = {edge.source_id for edge in edges} | {edge.target_id for edge in edges}
    if asset_id:
        visible_ids.add(asset_id)
    visible_assets = [asset for asset in assets if asset.id in visible_ids]
    visible_by_id = {asset.id: asset for asset in visible_assets}
    graph_columns: list[tuple[str, list[Asset]]] = []
    if asset_id and asset_id in visible_by_id:
        upstream_ids = {edge.source_id for edge in edges if edge.target_id == asset_id}
        downstream_ids = {edge.target_id for edge in edges if edge.source_id == asset_id}
        graph_columns = [
            ("Upstream", [visible_by_id[item] for item in upstream_ids if item in visible_by_id]),
            ("Selected asset", [visible_by_id[asset_id]]),
            ("Downstream", [visible_by_id[item] for item in downstream_ids if item in visible_by_id]),
        ]
    else:
        ranks = {asset.id: 0 for asset in visible_assets}
        for _ in range(max(1, len(visible_assets))):
            changed = False
            for edge in edges:
                if edge.source_id in ranks and edge.target_id in ranks and ranks[edge.target_id] <= ranks[edge.source_id]:
                    ranks[edge.target_id] = ranks[edge.source_id] + 1
                    changed = True
            if not changed:
                break
        for rank in sorted(set(ranks.values())):
            graph_columns.append((f"Stage {rank + 1}", [asset for asset in visible_assets if ranks[asset.id] == rank]))
    graph_nodes = []
    for label, nodes in graph_columns:
        graph_nodes.append(Div(Span(label, cls="lineage-platform-label"), *[A(Span(f"{asset.platform} · {asset.asset_type.replace('_', ' ').title()}", cls="node-type"), Strong(asset.name), Small(asset.domain), href=f"/app/assets/{asset.id}", cls=f"lineage-node{' focus' if asset.id == asset_id else ''}", data_id=str(asset.id)) for asset in nodes], cls="lineage-platform-column"))
    edge_data = [Span(cls="lineage-edge-data", data_source=str(edge.source_id), data_target=str(edge.target_id), data_evidence=edge.evidence_type, data_label=edge.operation) for edge in edges]
    return app_shell(
        identity, "Lineage", "/app/lineage",
        page_intro("Lineage and impact", "See where data comes from and what depends on it", "Every relationship carries its evidence source. Manual and inferred edges remain visibly distinct from native lineage.", A("Manage gaps", href="/app/lineage/manage", cls="button button-outline") if identity.can("steward", "engineer") else ""),
        Form(Select(Option("All assets", value=""), *[Option(asset.name, value=str(asset.id), selected=(asset.id == asset_id)) for asset in assets], name="asset_id", aria_label="Focus asset"), Select(*[Option(v.title(),value=v,selected=direction==v) for v in ("both","upstream","downstream")],name="direction",aria_label="Impact direction"), Select(*[Option(f"{v} hop{'s' if v>1 else ''}",value=str(v),selected=depth==v) for v in range(1,6)],name="depth",aria_label="Impact depth"), Select(Option("All evidence", value=""), *[Option(item.replace("_", " ").title(), value=item, selected=(item == evidence)) for item in ("native", "query_history", "manual", "inferred")], name="evidence", aria_label="Evidence type"), Button("Update graph", type="submit", cls="button button-primary compact"), A("Reset", href="/app/lineage", cls="button button-quiet compact"), method="get", action="/app/lineage", cls="filter-row lineage-filters"),
        Div(Div(Span("Native", cls="legend-line native"), Span("Query history", cls="legend-line query"), Span("Manual", cls="legend-line manual"), cls="lineage-legend"), Span(f"{len(visible_assets)} assets · {len(edges)} relationships", cls="graph-count"), cls="graph-toolbar"),
        Div(Svg(cls="lineage-svg", aria_hidden="true"), *graph_nodes, *edge_data, id="lineage-graph", cls="lineage-graph", style=f"grid-template-columns:repeat({max(1, len(graph_columns))}, minmax(220px, 1fr))"),
        Div(Span("Evidence guide"), P("Native edges come from platform dependency services. Query-history edges are observed from executed transformations. Manual edges fill known gaps and carry lower confidence."), cls="evidence-note"),
        Section(section_header("Relationship evidence", "Column pairs appear when the source platform provides them"),Table(Thead(Tr(Th("Source"),Th("Source field"),Th("Operation"),Th("Target field"),Th("Target"),Th("Evidence"))),Tbody(*[Tr(Td(visible_by_id[e.source_id].name if e.source_id in visible_by_id else e.source_id),Td(Code(e.source_field) if e.source_field else "Table level"),Td(e.operation),Td(Code(e.target_field) if e.target_field else "Table level"),Td(visible_by_id[e.target_id].name if e.target_id in visible_by_id else e.target_id),Td(status_badge(e.evidence_type))) for e in edges]),cls="data-table"),cls="panel"),
        wide=True,
    )


def _sparkline(values: list[float]):
    if not values:
        return Span("No trend", cls="muted")
    low, high = min(values), max(values)
    span = high - low or 1
    points = " ".join(f"{index * 18},{32 - ((value - low) / span * 24):.1f}" for index, value in enumerate(values))
    return Svg(ft("polyline", points=points, fill="none", stroke="currentColor", stroke_width="2", stroke_linecap="round", stroke_linejoin="round"), viewBox="0 0 108 36", cls="sparkline", aria_label="Recent score trend")


def quality_page(identity: UserIdentity, repo: GovernanceRepository, status: str = ""):
    rules = repo.quality_rules(identity)
    if status:
        rules = [rule for rule in rules if rule.status == status]
    assets = {asset.id: asset for asset in repo.list_assets(identity=identity)}
    failed = sum(rule.status in {"failed", "warning"} for rule in rules)
    avg = sum(rule.score for rule in rules) / len(rules) if rules else 0
    return app_shell(
        identity, "Data quality", "/app/quality",
        page_intro("Measurable trust", "Quality that creates accountable action", "Define expectations once, execute them close to the data, and connect every failure to an owner, steward, and remediation path.", A("Create rule", href="/app/quality/new", cls="button button-primary") if identity.can("steward", "engineer") else ""),
        Div(metric_card("Portfolio score", f"{avg:.1f}", "Average latest result", "green"), metric_card("Active rules", len(rules), "Versioned and scheduled", "blue"), metric_card("Needs attention", failed, "Failed or warning results", "amber"), metric_card("Coverage", "75%", "Critical assets with an active rule", "violet"), cls="metric-grid"),
        Div(A("All", href="/app/quality", cls=f"filter-chip{' active' if not status else ''}"), A("Passed", href="/app/quality?status=passed", cls=f"filter-chip{' active' if status == 'passed' else ''}"), A("Failed", href="/app/quality?status=failed", cls=f"filter-chip{' active' if status == 'failed' else ''}"), A("Warning", href="/app/quality?status=warning", cls=f"filter-chip{' active' if status == 'warning' else ''}"), cls="chip-row"),
        Div(*[quality_rule_card(rule, assets.get(rule.asset_id)) for rule in rules], cls="quality-grid") if rules else empty_state("No quality rules in this view", "Choose another status filter."),
    )


def quality_rule_card(rule: QualityRule, asset: Asset | None):
    return Article(
        Div(status_badge(rule.status if rule.enabled else "disabled"), Span(rule.severity.title(), cls=f"severity {rule.severity}"), cls="quality-card-head"),
        H3(rule.name),
        A(asset.name if asset else "Unknown asset", href=f"/app/assets/{rule.asset_id}", cls="quality-asset"),
        Div(Div(Strong(f"{rule.score:.1f}%"), Small("Latest score")), _sparkline(rule.trend), cls="quality-score-row"),
        Div(Span(rule.rule_type.title()), Span(rule.schedule.title()), Span(rule.last_run), cls="quality-meta"),
        Details(Summary("Rule expression"), Code(rule.expression), cls="rule-expression"),
        Div(A("Edit", href=f"/app/quality/{rule.id}/edit", cls="button button-quiet compact"), Form(Button("Run now", type="submit", cls="button button-outline compact",disabled=not rule.enabled), method="post", action=f"/app/quality/{rule.id}/run"),Form(Input(type="hidden",name="enabled",value="false" if rule.enabled else "true"),Button("Disable" if rule.enabled else "Enable",type="submit",cls="button button-quiet compact"),method="post",action=f"/app/quality/{rule.id}/enabled"), cls="form-actions"),
        cls="quality-card",
    )


def work_page(identity: UserIdentity, repo: GovernanceRepository, kind: str = "", status: str = ""):
    work = repo.work_items(kind, status, identity)
    counts = Counter(item.kind for item in repo.work_items(identity=identity))
    tabs = [("", "All"), ("quality", "Quality"), ("certification", "Certification"), ("metadata", "Metadata"), ("access", "Access"), ("attestation", "Attestation")]
    return app_shell(
        identity, "Stewardship", "/app/work",
        page_intro("Accountable work", "One queue for every governance responsibility", "Resolve quality, certify reusable assets, enrich context, approve access, and renew ownership without losing the audit trail."),
        Div(*[A(Span(label), Small(str(len(repo.work_items(identity=identity))) if not key else str(counts[key])), href=f"/app/work{'?kind=' + key if key else ''}", cls=f"queue-tab{' active' if kind == key else ''}") for key, label in tabs], cls="queue-tabs"),
        Div(
            Div(Strong(f"{len(work)} items"), Span("Ordered by priority and due date")),
            Form(Select(Option("All statuses", value=""), *[Option(value.replace("_", " ").title(), value=value, selected=(status == value)) for value in ("open", "in_progress", "waiting", "approved", "resolved", "rejected")], name="status", aria_label="Work status"), Input(type="hidden", name="kind", value=kind), Button("Filter", type="submit", cls="button button-outline compact"), method="get", action="/app/work", cls="filter-row"),
            cls="queue-toolbar",
        ),
        Div(*[work_item_card(item, repo) for item in work], cls="work-board") if work else empty_state("Queue is clear", "No work items match the selected filters."),
    )


def work_item_row(item: WorkItem, repo: GovernanceRepository):
    asset = repo.get_asset(item.asset_id)
    return A(Div(status_badge(item.kind), Div(Strong(item.title), Small(asset.name if asset else "Governance"))), Div(Span(item.priority.title(), cls=f"severity {item.priority}"), Small(item.due)), href=f"/app/work?kind={item.kind}", cls="work-row")


def work_item_card(item: WorkItem, repo: GovernanceRepository):
    asset = repo.get_asset(item.asset_id)
    next_actions = {
        "open": (("in_progress", "Start work"), ("rejected", "Reject")),
        "in_progress": (("resolved", "Resolve"), ("waiting", "Wait")),
        "waiting": (("in_progress", "Resume"), ("approved", "Approve")),
    }.get(item.status, ())
    return Article(
        Div(Div(status_badge(item.kind), Span(item.priority.title(), cls=f"severity {item.priority}")), status_badge(item.status), cls="work-card-head"),
        H3(item.title), P(item.description),
        A(asset.name if asset else "Governance item", href=f"/app/assets/{item.asset_id}", cls="work-asset") if asset else "",
        Div(Div(Span(item.assignee[:1].upper(), cls="mini-avatar"), Div(Small("Assigned to"), Strong(item.assignee))), Div(Small("Due"), Strong(item.due)), cls="work-card-meta"),
        Div(A("Open", href=f"/app/work/{item.id}", cls="button button-outline compact"), *[Form(Input(type="hidden", name="status", value=value), Button(label, type="submit", cls=f"button {'button-primary' if index == 0 else 'button-quiet'} compact"), method="post", action=f"/app/work/{item.id}/status", hx_post=f"/app/work/{item.id}/status", hx_target=f"#work-{item.id}", hx_swap="outerHTML") for index, (value, label) in enumerate(next_actions)], cls="work-card-actions"),
        id=f"work-{item.id}", cls="work-card",
    )


def glossary_page(identity: UserIdentity, repo: GovernanceRepository, query: str = ""):
    terms = repo.glossary(query, identity)
    domains = Counter(term.domain for term in terms)
    return app_shell(
        identity, "Glossary", "/app/glossary",
        page_intro("Shared language", "Definitions that travel with the data", "Agree business meaning once, assign an accountable owner, and connect it directly to the technical assets people use.", A("Create term", href="/app/glossary/new", cls="button button-primary") if identity.can("steward", "owner") else ""),
        Form(Div(icon("search"), Input(name="q", value=query, placeholder="Search terms and definitions", aria_label="Search glossary"), cls="catalog-search"), Button("Search", type="submit", cls="button button-primary compact"), method="get", action="/app/glossary", cls="glossary-search"),
        Div(*[Span(Strong(str(count)), f" {domain}") for domain, count in sorted(domains.items())], cls="domain-summary"),
        Div(*[Article(Div(Span(term.domain, cls="term-domain"), status_badge(term.status)), H3(term.name), P(term.definition), Div(Span(f"Owner · {term.owner}"), Span(f"{term.linked_assets} linked assets")), A("Edit", href=f"/app/glossary/{term.id}/edit", cls="inline-link") if identity.can("steward", "owner") else "", cls="term-card") for term in terms], cls="term-grid") if terms else empty_state("No glossary terms found", "Try a broader business term."),
    )


def adapters_page(identity: UserIdentity, repo: GovernanceRepository):
    adapters = repo.adapters(identity)
    return app_shell(
        identity, "Administration", "/app/admin/adapters",
        page_intro("Platform connections", "Adapters with explicit capability boundaries", "Credentials are injected into workers through secret references. FastDataGov stores connection configuration, cursors, health, and audit evidence—not plaintext secrets."),
        Div(*[Article(
            Div(Div(Span(adapter.key[:1].upper(), cls=f"adapter-logo {adapter.key}"), Div(H3(adapter.name), P(adapter.message or "Connection is operating normally."))), status_badge(adapter.status), cls="adapter-card-head"),
            Div(Div(Span("Last sync"), Strong(adapter.last_sync)), Div(Span("Assets"), Strong(str(adapter.assets))), Div(Span("Health"), Strong(adapter.health)), cls="adapter-metrics"),
            Div(*[Div(Span(key.replace("_", " ").title()), status_badge(value)) for key, value in adapter.capabilities.items()], cls="capability-list"),
            Div(A("Configure and test", href="/app/admin/connections", cls="button button-outline compact"), A("View jobs",href="/app/admin/jobs",cls="button button-primary compact"), cls="adapter-actions"),
            cls="adapter-card",
        ) for adapter in adapters], cls="adapter-grid"),
        Section(section_header("Security posture", "Defaults applied to every connection"), Div(Div(Strong("Least privilege"), P("Dedicated read roles and isolated quality warehouses.")), Div(Strong("Secret references"), P("Credentials remain in the deployment secret manager.")), Div(Strong("Source-aware visibility"), P("Imported grants constrain catalog discovery for ordinary users.")), cls="security-grid"), cls="panel"),
    )


def work_item_partial(item: WorkItem, repo: GovernanceRepository):
    return work_item_card(item, repo)


def products_page(identity: UserIdentity, repo: GovernanceRepository):
    products = repo.products(identity)
    assets = {asset.id: asset for asset in repo.list_assets(identity=identity)}
    return app_shell(
        identity, "Data products", "/app/products",
        page_intro("Reuse", "Governed data products", "Package trusted assets with ownership, service expectations, access guidance, and evidence consumers can assess.", A("Create product", href="/app/products/new", cls="button button-primary") if identity.can("steward", "owner") else ""),
        Div(*[Article(
            Div(status_badge(product.status), status_badge(product.certification), cls="work-card-head"),
            H3(product.name), P(product.description),
            Div(Span(product.domain), Span(f"{len(product.asset_ids)} assets"), cls="quality-meta"),
            Dl(Dt("Owner"), Dd(product.owner), Dt("Steward"), Dd(product.steward), Dt("Service level"), Dd(product.service_level), Dt("Access"), Dd(product.access_guidance), cls="definition-list"),
            Div(*[A(assets[aid].name, href=f"/app/assets/{aid}", cls="tag") for aid in product.asset_ids if aid in assets], cls="tag-list"),
            A("Edit product", href=f"/app/products/{product.id}/edit", cls="inline-link") if identity.can("steward", "owner") else "",
            Form(Select(*[Option(v.title(),value=v) for v in ("certified","verified","rejected")],name="status"),Input(type="number",name="expires_days",value="365",min="1",max="1825",aria_label="Certification duration"),Input(name="notes",placeholder="Decision notes"),Button("Certify",type="submit",cls="button button-primary compact"),method="post",action=f"/app/products/{product.id}/certify",cls="inline-form") if identity.can("owner","governance_lead") else "",
            cls="product-card",
        ) for product in products], cls="product-grid") if products else empty_state("No data products", "Create a reusable package from governed assets."),
    )


def product_form_page(identity, repo, product=None):
    assets = repo.list_assets(identity=identity)
    selected = set(product.asset_ids if product else [])
    domains = repo.domains()
    action = f"/app/products/{product.id}/save" if product else "/app/products/save"
    return app_shell(identity, "Edit data product" if product else "New data product", "/app/products",
        page_intro("Product authoring", "Describe a reusable data product", "Ownership, service expectations, access and linked assets travel together."),
        Form(
            Div(Label("Name", Input(name="name", value=product.name if product else "", required=True)), Label("Domain", Select(*[Option(d.name, value=d.name, selected=bool(product and d.name == product.domain)) for d in domains], name="domain", required=True)), cls="form-grid"),
            Label("Business description", Textarea(product.description if product else "", name="description", rows="4", required=True)),
            Div(Label("Owner email", Input(type="email", name="owner", value=product.owner if product else identity.email, required=True)), Label("Steward email", Input(type="email", name="steward", value=product.steward if product else identity.email, required=True)), cls="form-grid"),
            Div(Label("Status", Select(*[Option(v.title(), value=v, selected=bool(product and product.status == v)) for v in ("draft","active","deprecated")], name="status")), Label("Service level", Input(name="service_level", value=product.service_level if product else "Daily refresh")), cls="form-grid"),
            Label("Access guidance", Textarea(product.access_guidance if product else "", name="access_guidance", rows="3")),
            Fieldset(Legend("Included assets"), *[Label(Input(type="checkbox", name="asset_ids", value=str(a.id), checked=a.id in selected), f" {a.name} · {a.platform}", cls="check-row") for a in assets], cls="check-list"),
            Div(Button("Save product", type="submit", cls="button button-primary"), A("Cancel", href="/app/products", cls="button button-quiet"), cls="form-actions"), method="post", action=action, cls="governance-form panel"),
    )


def asset_edit_page(identity, repo, asset):
    glossary = repo.glossary(identity=identity)
    linked = set(asset.terms)
    return app_shell(identity, f"Edit {asset.name}", "/app/catalog",
        page_intro("Metadata authoring", "Improve business context", "Technical metadata stays adapter-owned; business meaning, accountability and classifications are versioned here."),
        Form(
            Label("Business description", Textarea(asset.business_description, name="business_description", rows="5", required=True)),
            Div(Label("Owner email", Input(type="email", name="owner", value=asset.owner, required=True)), Label("Steward email", Input(type="email", name="steward", value=asset.steward, required=True)), cls="form-grid"),
            Div(Label("Sensitivity", Select(*[Option(v.title(), value=v, selected=asset.sensitivity == v) for v in ("public","internal","confidential","restricted")], name="sensitivity")), Label("Business tags", Input(name="tags", value=", ".join(asset.tags), placeholder="gold, reusable, regulated")), cls="form-grid"),
            Label("Access guidance", Textarea(asset.access_guidance, name="access_guidance", rows="3")),
            Fieldset(Legend("Glossary terms"), *[Label(Input(type="checkbox", name="term_ids", value=str(term.id), checked=term.name in linked), f" {term.name}", cls="check-row") for term in glossary], cls="check-list"),
            Details(Summary("Optional native tag write-back"),Div(Label("Fully qualified native tag",Input(name="native_tag_name",placeholder="GOVERNANCE.TAGS.SENSITIVITY")),Label("Value",Input(name="native_tag_value",placeholder="CONFIDENTIAL")),cls="form-grid"),P("The worker validates the platform identifier and uses the configured connection permissions. Leave blank to keep tags only in FastDataGov."),cls="rule-expression"),
            Div(Button("Save metadata", type="submit", cls="button button-primary"), A("Cancel", href=f"/app/assets/{asset.id}", cls="button button-quiet"), cls="form-actions"), method="post", action=f"/app/assets/{asset.id}/metadata", cls="governance-form panel"),
    )


def glossary_form_page(identity, repo, term=None):
    domains = repo.domains()
    return app_shell(identity, "Glossary authoring", "/app/glossary",
        page_intro("Shared language", "Define a governed term", "Each revision preserves its previous meaning and records the responsible editor."),
        Form(
            Div(Label("Term", Input(name="name", value=term.name if term else "", required=True)), Label("Domain", Select(*[Option(d.name, value=d.name, selected=bool(term and term.domain == d.name)) for d in domains], name="domain", required=True)), cls="form-grid"),
            Label("Definition", Textarea(term.definition if term else "", name="definition", rows="6", required=True)),
            Div(Label("Owner email", Input(type="email", name="owner", value=term.owner if term else identity.email, required=True)), Label("Status", Select(*[Option(v.replace('_',' ').title(), value=v, selected=bool(term and term.status == v)) for v in ("draft","in_review","approved","deprecated")], name="status")), cls="form-grid"),
            Div(Button("Save term", type="submit", cls="button button-primary"), A("Cancel", href="/app/glossary", cls="button button-quiet"), cls="form-actions"), method="post", action=f"/app/glossary/{term.id}/save" if term else "/app/glossary/save", cls="governance-form panel"),
    )


def lineage_manage_page(identity, repo):
    assets = repo.list_assets(identity=identity)
    by_id = {a.id:a for a in assets}
    manual = [e for e in repo.lineage(identity=identity) if e.evidence_type == "manual"]
    options = lambda: [Option(f"{a.name} · {a.platform}", value=str(a.id)) for a in assets]
    return app_shell(identity, "Manage lineage", "/app/lineage",
        page_intro("Lineage authoring", "Fill evidence gaps safely", "Manual relationships are visibly labelled, confidence-scored, auditable, and removable without touching native evidence."),
        Form(Div(Label("Upstream source", Select(*options(), name="source_id", required=True)), Label("Downstream target", Select(*options(), name="target_id", required=True)), cls="form-grid"), Div(Label("Operation", Input(name="operation", value="transforms", required=True)), Label("Confidence", Input(type="number", name="confidence", min="0", max="1", step="0.01", value="0.75")), cls="form-grid"), Button("Add relationship", type="submit", cls="button button-primary"), method="post", action="/app/lineage/create", cls="governance-form panel"),
        Section(section_header("Manual relationships", "Only manually asserted evidence can be removed"), Div(*[Div(Span(f"{by_id[e.source_id].name} → {by_id[e.target_id].name}"), Span(f"{e.operation} · {e.confidence:.0%}"), Form(Button("Remove", type="submit", cls="text-button danger"), method="post", action=f"/app/lineage/{e.id}/delete"), cls="admin-row") for e in manual if e.source_id in by_id and e.target_id in by_id], cls="admin-list") if manual else empty_state("No manual relationships", "Native and observed lineage remains available in the graph."), cls="panel"),
    )


def quality_form_page(identity, repo, rule=None):
    assets=repo.list_assets(identity=identity)
    return app_shell(identity, "Quality rule", "/app/quality",
        page_intro("Quality authoring", "Define a measurable expectation", "Rules execute through the source adapter; each update creates an immutable revision."),
        Form(
            Label("Asset", Select(*[Option(f"{a.name} · {a.platform}", value=str(a.id), selected=bool(rule and rule.asset_id == a.id)) for a in assets], name="asset_id", required=True)),
            Div(Label("Rule name", Input(name="name", value=rule.name if rule else "", required=True)), Label("Type", Select(*[Option(v.replace('_',' ').title(), value=v, selected=bool(rule and rule.rule_type == v)) for v in ("completeness","uniqueness","validity","consistency","freshness","custom_sql","custom_python")], name="rule_type")), cls="form-grid"),
            Label("Predicate or implementation", Textarea(rule.expression if rule else "", name="expression", rows="5", placeholder="CUSTOMER_ID IS NOT NULL", required=True)),
            Div(Label("Pass threshold", Input(type="number", name="threshold", min="0", max="100", step="0.01", value="95")), Label("Severity", Select(*[Option(v.title(), value=v, selected=bool(rule and rule.severity == v)) for v in ("low","medium","high","critical")], name="severity")), Label("Schedule", Select(*[Option(v.title(), value=v, selected=bool(rule and rule.schedule == v)) for v in ("hourly","daily","weekly","manual")], name="schedule")), cls="form-grid three"),
            Div(Button("Save rule", type="submit", cls="button button-primary"), A("Cancel", href="/app/quality", cls="button button-quiet"), cls="form-actions"), method="post", action=f"/app/quality/{rule.id}/save" if rule else "/app/quality/save", cls="governance-form panel"),
    )


def work_detail_page(identity, repo, item):
    comments=repo.work_comments(item.id); asset=repo.get_asset(item.asset_id, identity)
    return app_shell(identity, item.title, "/app/work",
        Div(A("Stewardship", href="/app/work"), Span("/"), Span(item.title), cls="breadcrumbs"),
        Article(Div(status_badge(item.kind), status_badge(item.status), cls="work-card-head"), H2(item.title), P(item.description), Dl(Dt("Asset"), Dd(A(asset.name, href=f"/app/assets/{asset.id}") if asset else "Governance"), Dt("Assignee"), Dd(item.assignee), Dt("Priority"), Dd(item.priority.title()), Dt("Due"), Dd(item.due), cls="definition-list"), cls="panel"),
        Section(section_header("Discussion", "Decisions and remediation context remain with the workflow"), Div(*[Div(Strong(c.author_email), P(c.body), Small(c.created_at), cls="comment") for c in comments], cls="comment-list") if comments else empty_state("No comments yet", "Add the first piece of context."), Form(Textarea(name="body", rows="3", placeholder="Add a decision, question, or remediation update", required=True), Button("Add comment", type="submit", cls="button button-primary compact"), method="post", action=f"/app/work/{item.id}/comments", cls="comment-form"), cls="panel"),
    )


def admin_page(identity, repo, section="domains"):
    tabs=(("connections","Connections"),("domains","Domains"),("accountability","Accountability"),("access","Access & roles"),("workflows","Workflows"),("notifications","Notifications"),("jobs","Jobs"),("audit","Audit"),("pilot","Pilot outcomes"))
    nav=Div(*[A(label, href=f"/app/admin/{key}", cls=f"queue-tab{' active' if section==key else ''}") for key,label in tabs], cls="queue-tabs")
    if section=="connections":
        connections=repo.connection_details()
        body=Div(Form(Div(Label("Key",Input(name="key",placeholder="snowflake-prod",required=True)),Label("Name",Input(name="name",placeholder="Snowflake production",required=True)),Label("Adapter",Select(*[Option(v.title(),value=v) for v in ("snowflake","fabric","databricks","demo")],name="adapter_type")),cls="form-grid three"),Label("Credential reference",Input(name="credential_ref",placeholder="env:SNOWFLAKE_PASSWORD")),Label("Non-secret JSON configuration",Textarea('{"account":"org-account","user":"FASTDATAGOV","warehouse":"GOVERNANCE_WH","role":"DATA_GOVERNANCE_READER","quality_warehouse":"GOVERNANCE_QUALITY_WH","quality_role":"DATA_QUALITY_EXECUTOR"}',name="config_json",rows="5")),Button("Save connection",type="submit",cls="button button-primary compact"),method="post",action="/app/admin/connections/save",cls="governance-form panel"),Div(*[Div(Div(Strong(c["name"]),Small(c["key"])),status_badge(c["status"]),Span(c["adapter_type"].title()),Div(Form(Input(type="hidden",name="kind",value="adapter.health"),Button("Test",type="submit",cls="button button-quiet compact"),method="post",action=f"/app/admin/connections/{c['key']}/job"),Form(Input(type="hidden",name="kind",value="adapter.sync"),Button("Sync",type="submit",cls="button button-outline compact"),method="post",action=f"/app/admin/connections/{c['key']}/job"),cls="form-actions"),cls="admin-row") for c in connections],cls="admin-list panel"))
    elif section=="domains":
        domains=repo.domains(); body=Div(Form(Div(Label("Name",Input(name="name",required=True)),Label("Parent",Select(Option("No parent",value=""),*[Option(d.name,value=str(d.id)) for d in domains],name="parent_id")),cls="form-grid"),Label("Description",Input(name="description")),Button("Add domain",type="submit",cls="button button-primary compact"),method="post",action="/app/admin/domains/save",cls="governance-form panel"),Div(*[Div(Div(Strong(d.name),Small(d.description or "No description")),Span(next((p.name for p in domains if p.id==d.parent_id),"Top level")),Details(Summary("Edit"),Form(Input(type="hidden",name="domain_id",value=str(d.id)),Input(name="name",value=d.name,required=True),Input(name="description",value=d.description),Select(Option("No parent",value=""),*[Option(p.name,value=str(p.id),selected=p.id==d.parent_id) for p in domains if p.id!=d.id],name="parent_id"),Button("Save",type="submit",cls="button button-primary compact"),method="post",action="/app/admin/domains/save",cls="mini-form")),cls="admin-row") for d in domains],cls="admin-list panel"))
    elif section=="accountability":
        assignments=repo.assignments(); body=Div(Form(Div(Label("Scope type",Select(*[Option(v.title(),value=v) for v in ("asset","domain","product")],name="scope_type")),Label("Scope ID",Input(type="number",name="scope_id",min="1",required=True)),Label("Responsibility",Select(Option("Owner",value="owner"),Option("Steward",value="steward"),name="responsibility")),cls="form-grid three"),Div(Label("Assignee email",Input(type="email",name="email",required=True)),Label("Attestation validity (days)",Input(type="number",name="expires_days",min="1",max="1825",value="365")),cls="form-grid"),Button("Assign and attest",type="submit",cls="button button-primary compact"),method="post",action="/app/admin/accountability/save",cls="governance-form panel"),Div(*[Div(Div(Strong(a.assignee_email),Small(a.responsibility.title())),Span(f"{a.scope_type}:{a.scope_id}"),Span(a.expires_at or "No expiry"),cls="admin-row") for a in assignments],cls="admin-list panel") if assignments else empty_state("No scoped assignments", "Asset owner and steward fields remain visible; create formal attestable assignments here."))
    elif section=="access":
        roles=repo.roles(); aliases=repo.principal_aliases()
        body=Div(
            Form(Div(Label("Principal type",Select(Option("User",value="user"),Option("Group",value="group"),name="principal_type")),Label("Email or group ID",Input(name="principal_key",required=True)),cls="form-grid"),Label("Global application role",Select(*[Option(v.replace('_',' ').title(),value=v) for v in ("consumer","steward","owner","engineer","governance_lead","admin")],name="role")),Input(type="hidden",name="scope_type",value="global"),Button("Add role binding",type="submit",cls="button button-primary compact"),method="post",action="/app/admin/roles/save",cls="governance-form panel"),
            Div(*[Div(Div(Strong(r["principal_key"]),Small(r["principal_type"])),Span(r["role"].replace('_',' ').title()),Span(f"{r['scope_type']} {r['scope_key']}"),Form(Button("Revoke",type="submit",cls="text-button danger"),method="post",action=f"/app/admin/roles/{r['id']}/delete"),cls="admin-row") for r in roles],cls="admin-list panel"),
            Section(section_header("Source principal aliases","Map an Entra user/group identifier to a Snowflake role or another imported platform principal"),Form(Div(Label("Identity type",Select(Option("User",value="user"),Option("Group",value="group"),name="identity_principal_type")),Label("Identity key",Input(name="identity_key",required=True)),Label("Platform",Input(name="platform_key",placeholder="snowflake",required=True)),Label("Source principal",Input(name="source_principal_key",placeholder="ANALYST_ROLE",required=True)),cls="form-grid"),Button("Add alias",type="submit",cls="button button-primary compact"),method="post",action="/app/admin/aliases/save",cls="governance-form"),Div(*[Div(Div(Strong(a["identity_key"]),Small(a["identity_principal_type"])),Span(a["platform_key"]),Span(a["source_principal_key"]),Form(Button("Remove",type="submit",cls="text-button danger"),method="post",action=f"/app/admin/aliases/{a['id']}/delete"),cls="admin-row") for a in aliases],cls="admin-list"),cls="panel"),
        )
    elif section=="workflows":
        body=Div(*[Form(Div(Div(Strong(w["display_name"]),Small(w["kind"])),Label("Due days",Input(type="number",name="due_days",min="1",value=str(w["due_days"]))),Label("Approval role",Input(name="approval_role",value=w["approval_role"])),Label(Input(type="checkbox",name="enabled",value="true",checked=w["enabled"])," Enabled",cls="check-row"),Button("Save",type="submit",cls="button button-outline compact"),cls="admin-row"),method="post",action=f"/app/admin/workflows/{w['kind']}/save") for w in repo.workflow_definitions()],cls="admin-list panel")
    elif section=="notifications":
        channels=repo.notification_channels(); body=Div(Form(Div(Label("Key",Input(name="key",required=True)),Label("Type",Select(*[Option(v.title(),value=v) for v in ("email","teams","slack","webhook")],name="channel_type")),cls="form-grid"),Label("Endpoint secret reference",Input(name="endpoint_ref",placeholder="env:GOVERNANCE_TEAMS_WEBHOOK",required=True)),Label("Events",Input(name="events",placeholder="workflow.created, quality.failed")),Label(Input(type="checkbox",name="enabled",value="true",checked=True)," Enabled",cls="check-row"),Button("Save channel",type="submit",cls="button button-primary compact"),method="post",action="/app/admin/notifications/save",cls="governance-form panel"),Div(*[Div(Div(Strong(c["key"]),Small(c["channel_type"])),status_badge("healthy" if c["enabled"] else "disabled"),Span(c["endpoint_ref"]),Small(", ".join(c["events"]) or "All events"),cls="admin-row") for c in channels],cls="admin-list panel") if channels else empty_state("No notification channels", "Add email, Teams, Slack or webhook delivery using an environment-secret reference."))
    elif section=="jobs":
        body=Div(*[Div(Div(Strong(j.kind),Small(j.run_after)),status_badge(j.status),Span(f"{j.attempts} attempts"),Small(j.last_error),cls="admin-row") for j in repo.jobs()],cls="admin-list panel")
    elif section=="audit":
        body=Div(*[Div(Div(Strong(e.action),Small(e.actor)),Span(e.entity),Small(e.occurred_at),cls="admin-row") for e in repo.audit(100,identity)],cls="admin-list panel")
    else:
        body=Div(*[Article(Span(m.label,cls="metric-label"),Div(Strong(str(m.current_value if m.current_value is not None else "—"),cls="metric-value"),Span(f"Target {m.target} {m.unit}")),P(m.notes),cls="metric-card") for m in repo.pilot_metrics()],cls="metric-grid")
    return app_shell(identity,"Administration","/app/admin/adapters",page_intro("Administration","Governance operating controls","Manage the hierarchy, authorization, execution evidence and measurable adoption outcomes."),nav,body,wide=True)
