"""Public product, feature, and comparison pages for FastDataGov."""
from __future__ import annotations

from fasthtml.common import *

from fastdatagov.models import UserIdentity
from fastdatagov.web.components import logo, site_head

PARTNERS = (
    ("SAASPASS", "https://saaspass.com/", "https://saaspass.com/_next/static/assets/0176aeff921f6359fee88e796be31ace.png", "Full-stack identity and access management spanning MFA, SSO, passwordless access and integration APIs."),
    ("Sixty Four", "https://sixtyfour.ee/", "https://sixtyfour.ee/favicon.ico", "A senior Tallinn technology studio delivering software, AI consultancy, service design and public-sector programmes."),
    ("EDI Labs", "https://edilabs.tech/", "https://edilabs.tech/static/favicon.svg", "AI and data engineering for document intelligence, forecasting, geospatial systems and agentic workflows."),
    ("Predictive Labs", "https://predictivelabs.ai/", "https://predictivelabs.ai/static/favicon.svg", "Auditable AI systems for health, defence, public management, mobility and financial services."),
    ("Consistente", "https://consistente.tech/", "https://consistente.tech/static/favicon.svg", "Enterprise AI delivery across financial services, healthcare, the public sector and technology."),
)


FEATURE_CATALOG = (
    ("Unified data catalog", "Search technical and business metadata across connected platforms with owners, domains, classifications, freshness, and trust signals.", "Available"),
    ("Business glossary", "Define shared language, connect terms to assets, and version business definitions without changing source-platform metadata.", "Available"),
    ("Lineage & impact", "Explore upstream and downstream dependencies, column evidence, pipeline context, confidence, and manually curated gaps.", "Available"),
    ("Data quality", "Version, schedule, and run completeness, uniqueness, validity, freshness, custom SQL, and trusted Python checks near the data.", "Available"),
    ("Stewardship work", "Route quality issues, access requests, metadata enrichment, certifications, and attestations through accountable queues.", "Available"),
    ("Ownership & certification", "Assign owners and stewards by asset or data product, record attestations, and renew expiring certifications.", "Available"),
    ("Reusable data products", "Package governed assets with service levels, access guidance, accountability, certification, and quality context.", "Available"),
    ("Trust & audit", "Make quality scores, usage, validation dates, change history, adapter health, and audit evidence visible in one place.", "Available"),
    ("Identity & access", "Use Google or Microsoft Entra OIDC, platform-aware discovery grants, scoped roles, and source visibility controls.", "Available"),
    ("Snowflake adapter", "Extract assets, fields, tags, usage, grants, object and column lineage; execute guarded quality SQL and optional tag write-back.", "Pilot-ready"),
    ("Microsoft Fabric adapter", "A complete adapter contract and capability manifest ready for tenant-specific Fabric API and service-principal transport.", "Contract-ready"),
    ("Databricks adapter", "A complete adapter contract and capability manifest ready for Unity Catalog, workspace, and SQL warehouse transport.", "Contract-ready"),
)


COMPARISONS = (
    {
        "name": "FastDataGov",
        "model": "MIT · self-hosted",
        "fit": "Teams wanting a focused, business-friendly governance layer with a small Python/PostgreSQL operating surface",
        "lineage": "Snowflake table + column evidence, impact analysis, and manual gap capture",
        "quality": "Scheduled source-side SQL/Python checks, trends, issues, and trust scores",
        "governance": "Owners, stewards, attestations, certifications, work queues, glossary, data products, and audit",
        "tradeoff": "Newer connector ecosystem; Fabric and Databricks transports are contract-ready rather than generally available",
        "source": "https://github.com/predictivelabsai/FastDataGov",
        "source_label": "Source & licence",
        "highlight": True,
    },
    {
        "name": "OpenMetadata",
        "model": "Apache 2.0 · self-hosted / Collate",
        "fit": "Teams seeking a broad metadata, discovery, governance, quality, and observability platform",
        "lineage": "Table and column lineage across databases, pipelines, dashboards, and dbt",
        "quality": "Profiling, tests, alerts, and observability integrated with catalog context",
        "governance": "Glossary, classification, domains, data products, RBAC, collaboration, and metadata versioning",
        "tradeoff": "Broader platform and connector estate means a larger deployment and operating footprint",
        "source": "https://docs.open-metadata.org/v1.12.x/features",
        "license": "https://github.com/open-metadata/OpenMetadata",
        "source_label": "Official features",
    },
    {
        "name": "DataHub",
        "model": "Apache 2.0 · self-hosted / DataHub Cloud",
        "fit": "Platform engineering teams prioritising an extensible metadata graph and a large integration ecosystem",
        "lineage": "Automated table and column lineage with upstream/downstream impact analysis",
        "quality": "Profiles, assertions, anomaly detection, incidents, observability, and data contracts",
        "governance": "Search, ownership, domains, glossary, policies, classifications, forms, and APIs/SDKs",
        "tradeoff": "The full open-source stack includes several services such as GMS, search, database, and Kafka",
        "source": "https://docs.datahub.com/",
        "license": "https://github.com/datahub-project/datahub",
        "source_label": "Official docs",
    },
    {
        "name": "Atlan",
        "model": "Commercial SaaS",
        "fit": "Enterprises wanting a managed active-metadata and AI context platform with a broad connector catalogue",
        "lineage": "Automated cross-system, column-level lineage with propagation and in-line actions",
        "quality": "Quality signals and governance context brought together through platform apps and integrations",
        "governance": "Data marketplace, policies, classifications, business context, workflows, and context agents",
        "tradeoff": "Commercial subscription and vendor-managed operating model; no public open-source platform edition",
        "source": "https://atlan.com/data-discovery-catalog/",
        "source_label": "Official product",
    },
    {
        "name": "Collibra",
        "model": "Commercial platform",
        "fit": "Large enterprises needing a mature governance operating model, catalog, marketplace, lineage, and quality portfolio",
        "lineage": "Technical lineage and impact context integrated into catalog assets",
        "quality": "Profiling, samples, data quality context, and dedicated quality capabilities",
        "governance": "Stewardship operating models, policy, privacy, marketplace, catalog, and extensive integrations",
        "tradeoff": "Enterprise procurement and implementation model; no public open-source platform edition",
        "source": "https://www.collibra.com/products/data-catalog",
        "source_label": "Official product",
    },
    {
        "name": "Alation",
        "model": "Commercial platform",
        "fit": "Enterprises prioritising established catalog adoption, discovery, governance, and business-user search",
        "lineage": "Technical and business lineage from sources through pipelines, reports, and downstream use",
        "quality": "Quality indicators, trust flags, endorsements, and partner/source quality context",
        "governance": "Catalog, glossary, policies, stewardship, usage context, recommendations, and trust signals",
        "tradeoff": "Commercial platform with quote-led adoption; no public open-source platform edition",
        "source": "https://www.alation.com/product/data-catalog/",
        "source_label": "Official product",
    },
)


def _public_nav(identity: UserIdentity | None = None):
    return Header(
        logo(),
        Nav(
            A("Features", href="/features"),
            A("How we compare", href="/compare"),
            A("Architecture", href="/#architecture"),
            A("Partners", href="/#partners"),
            A("GitHub", href="https://github.com/predictivelabsai/FastDataGov", target="_blank", rel="noreferrer"),
            aria_label="Public navigation",
        ),
        A("Open workspace" if identity else "Sign in", href="/app" if identity else "/auth/login", cls="button button-outline"),
        cls="landing-nav",
    )


def _public_footer():
    return Footer(
        Div(logo(), P("Open-source data governance for modern data platforms.")),
        Div(
            A("Features", href="/features"),
            A("Comparison", href="/compare"),
            A("MIT License", href="https://github.com/predictivelabsai/FastDataGov/blob/main/LICENSE"),
            A("Source", href="https://github.com/predictivelabsai/FastDataGov"),
        ),
        cls="landing-footer",
    )


def _comparison_table(compact: bool = False):
    items = COMPARISONS[:4] if compact else COMPARISONS
    rows = []
    for item in items:
        sources = [A(item["source_label"] + " ↗", href=item["source"], target="_blank", rel="noreferrer", cls="comparison-source")]
        if item.get("license"):
            sources.append(A("Licence ↗", href=item["license"], target="_blank", rel="noreferrer", cls="comparison-source"))
        cells = [
            Td(Div(item["name"], cls="comparison-name"), *sources),
            Td(item["model"]),
            Td(item["fit"]),
            Td(item["lineage"]),
        ]
        if not compact:
            cells.extend((Td(item["quality"]), Td(item["governance"]), Td(item["tradeoff"])))
        rows.append(Tr(*cells, cls="comparison-fast" if item.get("highlight") else ""))
    headings = ["Platform", "Source / delivery", "Best fit", "Lineage"]
    if not compact:
        headings.extend(("Quality", "Governance", "Consider"))
    return Div(
        Table(
            Caption("Capabilities and delivery models checked against official product documentation on 9 August 2026."),
            Thead(Tr(*[Th(label) for label in headings])),
            Tbody(*rows),
            cls="comparison-table" + (" compact" if compact else ""),
        ),
        cls="comparison-scroll",
    )


def _partner_section():
    return Section(
        Div(Span("Partners", cls="eyebrow"), H2("Connect with trusted integration specialists."), P("Identity, software delivery, data engineering and applied-AI expertise for FastSME implementations."), cls="section-lead"),
        Div(*[
            A(Div(Img(src=logo_url, alt=f"{name} logo", loading="lazy"), Span("Integration Partner"), cls="partner-card-head"), H3(name), P(description), Small("Visit website ↗"), href=url, target="_blank", rel="noopener noreferrer", cls="partner-card")
            for name, url, logo_url, description in PARTNERS
        ], cls="partner-grid"),
        id="partners", cls="landing-section partner-section",
    )


def landing_page(identity: UserIdentity | None = None):
    primary_href = "/app" if identity else "/auth/login"
    primary_label = "Open workspace" if identity else "Sign in with Google"
    features = FEATURE_CATALOG[:6]
    return Html(
        site_head("Open data governance", "A business-friendly, MIT-licensed catalog for discovery, lineage, quality, stewardship, and ownership.", "/"),
        Body(
            _public_nav(identity),
            Main(
                Section(
                    Div(
                        Span("MIT-licensed data governance", cls="eyebrow"),
                        H1("Know which data to trust — and why."),
                        P("FastDataGov turns technical metadata into a shared business workspace for discovery, lineage, quality, stewardship, ownership, and reusable data products."),
                        Div(A(primary_label, href=primary_href, cls="button button-primary"), A("See every feature", href="/features", cls="button button-quiet"), cls="hero-actions"),
                        Div(Span("MIT licensed"), Span("Self-hosted"), Span("PostgreSQL core"), Span("Adapter-first"), cls="proof-row"),
                        cls="hero-copy",
                    ),
                    Div(
                        Div(
                            Div(Span("Trust overview"), Span("Live", cls="live-chip"), cls="preview-head"),
                            Div(Div(Span("Catalog coverage"), Strong("96%"), Small("Across connected sources")), Div(Span("Quality score"), Strong("94.5"), Small("+2.1 this quarter")), cls="preview-metrics"),
                            Div(
                                Div(Span("Certified"), Strong("Daily revenue"), Small("Snowflake · Finance"), Span("99.1", cls="preview-score")),
                                Div(Span("Needs attention"), Strong("Support case"), Small("Snowflake · Customer"), Span("78.0", cls="preview-score warn")),
                                Div(Span("Ready to review"), Strong("Customer 360"), Small("Cross-platform product"), Span("88.8", cls="preview-score info")),
                                cls="preview-list",
                            ),
                            cls="product-preview",
                        ),
                        Span("Evidence, not decoration", cls="preview-note"),
                        cls="hero-visual",
                    ),
                    cls="landing-hero",
                ),
                Section(
                    Div(Span("From catalog to accountability", cls="eyebrow"), H2("Governance people can actually use."), P("Every capability connects technical evidence to the owner, decision, quality signal, or workflow that makes data trustworthy."), cls="section-lead"),
                    Div(*[Article(Span(f"0{index}", cls="feature-number"), H3(name), P(description)) for index, (name, description, _status) in enumerate(features, 1)], cls="feature-grid"),
                    Div(A("Explore all 12 capabilities →", href="/features", cls="inline-link"), cls="section-action"),
                    id="capabilities",
                    cls="landing-section tint-section",
                ),
                Section(
                    Div(Span("Architecture", cls="eyebrow"), H2("Open at the core. Native at the edges."), P("FastHTML keeps interaction direct. PostgreSQL holds durable governance records. Python adapters execute close to each data platform."), cls="section-lead"),
                    Div(
                        Div(Span("Business workspace"), Strong("FastHTML"), Small("Search · Lineage · Quality · Workflows"), cls="architecture-node primary"),
                        Div(Span("Governance record"), Strong("PostgreSQL"), Small("Metadata · Trust · Audit · Jobs"), cls="architecture-node"),
                        Div(Span("Platform adapters"), Strong("Python"), Small("Snowflake · Fabric · Databricks"), cls="architecture-node"),
                        cls="architecture-row",
                    ),
                    id="architecture",
                    cls="landing-section",
                ),
                Section(
                    Div(Span("How it compares", cls="eyebrow"), H2("A focused open-source choice."), P("FastDataGov favours a smaller operating surface and explicit business accountability. Broader platforms may suit teams that need hundreds of connectors or a managed enterprise suite."), cls="section-lead"),
                    _comparison_table(compact=True),
                    Div(A("Read the full source-linked comparison →", href="/compare", cls="inline-link"), cls="section-action"),
                    cls="landing-section comparison-section",
                ),
                _partner_section(),
                Section(Span("Built for accountable reuse", cls="eyebrow"), H2("Make trusted data the easiest data to find."), A(primary_label, href=primary_href, cls="button button-primary"), cls="landing-cta"),
            ),
            _public_footer(),
            cls="landing-body",
        ),
        lang="en",
    )


def features_page(identity: UserIdentity | None = None):
    cards = []
    for name, description, status in FEATURE_CATALOG:
        status_class = status.lower().replace("-", "_")
        cards.append(Article(Div(Span(status, cls=f"feature-status {status_class}"), Span("Free · MIT", cls="feature-price"), cls="feature-meta"), H3(name), P(description), cls="feature-card"))
    return Html(
        site_head("Features", "Explore FastDataGov discovery, lineage, data quality, ownership, stewardship, adapter, and trust capabilities.", "/features"),
        Body(
            _public_nav(identity),
            Main(
                Section(Span("Features & availability", cls="eyebrow"), H1("One place to discover, trust, and govern data."), P("Available means implemented in the core platform. Pilot-ready identifies the production-capable Snowflake adapter. Contract-ready means the interface is complete while tenant transport still requires implementation."), Div(Span(Strong("9"), " core capabilities"), Span(Strong("1"), " pilot-ready adapter"), Span(Strong("2"), " contract-ready adapters"), cls="feature-summary"), cls="public-page-hero"),
                Section(Div(*cards, cls="feature-catalog"), cls="public-page-section tint-section"),
                Section(Div(Strong("Pricing: Free and MIT-licensed. "), "Infrastructure, implementation, support, and source-platform usage can still carry costs."), cls="public-note"),
            ),
            _public_footer(),
            cls="landing-body",
        ),
        lang="en",
    )


def comparison_page(identity: UserIdentity | None = None):
    return Html(
        site_head("Compare data governance platforms", "Compare FastDataGov with OpenMetadata, DataHub, Atlan, Collibra, and Alation using official product sources.", "/compare"),
        Body(
            _public_nav(identity),
            Main(
                Section(Span("How we compare", cls="eyebrow"), H1("Choose the operating model that fits."), P("A source-linked comparison across open-source and commercial data catalog, governance, lineage, and quality platforms. It separates software licensing from infrastructure and implementation effort."), Div(Span(Strong("MIT"), " FastDataGov licence"), Span(Strong("6"), " platforms reviewed"), Span(Strong("Official"), " vendor sources"), cls="feature-summary"), cls="public-page-hero"),
                Section(_comparison_table(), P("The matrix describes public product capabilities and delivery models, not a benchmark or guarantee. Validate connector depth, security, scale, service levels, and total operating cost against your own requirements.", cls="comparison-note"), cls="comparison-wrap"),
                Section(Span("FastDataGov's position", cls="eyebrow"), H2("Business accountability without a heavyweight control plane."), P("FastDataGov is strongest when Snowflake is the first production platform, business users need clear stewardship and ownership workflows, and teams value an inspectable Python/PostgreSQL stack. Choose a broader platform when immediate coverage across a very large connector estate matters more than a compact implementation."), A("Review every FastDataGov capability →", href="/features", cls="button button-primary"), cls="comparison-conclusion"),
            ),
            _public_footer(),
            cls="landing-body",
        ),
        lang="en",
    )
