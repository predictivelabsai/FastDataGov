from __future__ import annotations

from fasthtml.common import *

from fastdatagov.models import UserIdentity
from fastdatagov.web.components import icon, logo, site_head


def landing_page(identity: UserIdentity | None = None):
    primary_href = "/app" if identity else "/auth/login"
    primary_label = "Open workspace" if identity else "Sign in"
    features = [
        ("01", "Discover", "Find governed data across platforms with business context, owners, quality, and access guidance."),
        ("02", "Understand", "Follow evidence-backed lineage, assess downstream impact, and see how reusable data products are built."),
        ("03", "Improve", "Turn quality failures, certification, metadata, access, and attestation into accountable work."),
    ]
    return Html(
        site_head("Open data governance", "Discover, understand, and improve trusted data across every connected platform."),
        Body(
            Header(
                logo(),
                Nav(A("Capabilities", href="#capabilities"), A("Architecture", href="#architecture"), A("GitHub", href="https://github.com/predictivelabsai/FastDataGov", target="_blank", rel="noreferrer"), aria_label="Public navigation"),
                A(primary_label, href=primary_href, cls="button button-outline"),
                cls="landing-nav",
            ),
            Main(
                Section(
                    Div(
                        Span("Open-source data governance", cls="eyebrow"),
                        H1("Know which data to trust — and why."),
                        P("FastDataGov brings discovery, lineage, quality, stewardship, and ownership into one calm, business-friendly workspace."),
                        Div(A(primary_label, href=primary_href, cls="button button-primary"), A("Explore capabilities", href="#capabilities", cls="button button-quiet"), cls="hero-actions"),
                        Div(Span("MIT licensed"), Span("Self-hosted"), Span("Adapter-first"), Span("Source-aware access"), cls="proof-row"),
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
                    Div(Span("One governance layer", cls="eyebrow"), H2("A shared language for people and platforms."), P("Technical metadata stays connected to the decisions, responsibilities, and trust signals that make it useful."), cls="section-lead"),
                    Div(*[Article(Span(number, cls="feature-number"), H3(title), P(description)) for number, title, description in features], cls="feature-grid"),
                    id="capabilities",
                    cls="landing-section tint-section",
                ),
                Section(
                    Div(Span("Architecture", cls="eyebrow"), H2("Open at the core. Native at the edges."), P("FastHTML keeps the interaction model simple. PostgreSQL holds governed metadata and durable work. Python adapters meet every platform where it is."), cls="section-lead"),
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
                    Span("Built for accountable reuse", cls="eyebrow"),
                    H2("Make trusted data the easiest data to find."),
                    A(primary_label, href=primary_href, cls="button button-primary"),
                    cls="landing-cta",
                ),
            ),
            Footer(Div(logo(), P("Open-source data governance for modern data platforms.")), Div(A("MIT License", href="https://github.com/predictivelabsai/FastDataGov/blob/main/LICENSE"), A("Source", href="https://github.com/predictivelabsai/FastDataGov")), cls="landing-footer"),
            cls="landing-body",
        ),
        lang="en",
    )
