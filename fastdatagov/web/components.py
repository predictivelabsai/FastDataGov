from __future__ import annotations

from fasthtml.common import *

from fastdatagov.models import Asset, UserIdentity
from fastdatagov.config import settings


def site_head(title: str, description: str = "Open-source data governance"):
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content=description),
        Meta(name="theme-color", content="#ffffff"),
        Title(f"{title} · FastDataGov"),
        Link(rel="icon", href="/favicon.svg", type="image/svg+xml"),
        Link(rel="stylesheet", href="/styles.css"),
        Script(src="/app.js", defer=True),
    )


def icon(name: str, cls: str = ""):
    paths = {
        "home": "M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
        "search": "m21 21-4.35-4.35m2.35-5.65a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z",
        "catalog": "M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm4 3h8M8 12h8M8 16h5",
        "lineage": "M5 5h4v4H5zm10 10h4v4h-4zM7 9v3a3 3 0 0 0 3 3h5M15 5h4v4h-4zM9 7h6",
        "quality": "M4 12.5 9 17l11-11M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9",
        "work": "M9 5V3h6v2m-9 0h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm3 7 2 2 4-4",
        "glossary": "M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zm3 0v16M11 8h5M11 12h5",
        "admin": "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm8-3.5 2-1-2-3-2.2.3L16.5 6 17 4h-4l-.8 2-2.7.8L8 5 5 7l.7 2.2L4 11v3l1.7 1.8L5 18l3 2 1.5-1.8 2.7.8.8 2h4l-.5-2 1.3-2.3L20 17l2-3z",
        "arrow": "M5 12h14m-5-5 5 5-5 5",
        "user": "M20 21a8 8 0 0 0-16 0m8-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
    }
    return Svg(ft("path", d=paths.get(name, paths["catalog"])), viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke_width="1.8", stroke_linecap="round", stroke_linejoin="round", cls=f"icon {cls}".strip(), aria_hidden="true")


def logo(href: str = "/"):
    return A(
        Span(Span("F", cls="brand-letter"), cls="brand-mark", aria_hidden="true"),
        Span("FastDataGov", cls="brand-name"),
        href=href,
        cls="brand",
        aria_label="FastDataGov home",
    )


NAV_ITEMS = [
    ("Overview", "/app", "home"),
    ("Catalog", "/app/catalog", "catalog"),
    ("Data products", "/app/products", "catalog"),
    ("Lineage", "/app/lineage", "lineage"),
    ("Data quality", "/app/quality", "quality"),
    ("Stewardship", "/app/work", "work"),
    ("Glossary", "/app/glossary", "glossary"),
    ("Administration", "/app/admin/adapters", "admin"),
]


def app_shell(identity: UserIdentity, title: str, active: str, *content, wide: bool = False):
    nav = [
        A(icon(icon_name), Span(label), href=href, cls=f"side-link{' active' if active == href else ''}")
        for label, href, icon_name in NAV_ITEMS
    ]
    return Html(
        site_head(title),
        Body(
            A("Skip to content", href="#main-content", cls="skip-link"),
            Div(
                Aside(
                    Div(logo("/app"), Button("×", type="button", cls="mobile-close", data_action="toggle-nav", aria_label="Close navigation"), cls="side-head"),
                    Nav(*nav, cls="side-nav", aria_label="Workspace"),
                    Div(
                        Div(Span(identity.name[:1].upper(), cls="avatar"), Div(Strong(identity.name), Span(identity.email)), cls="user-summary"),
                        Form(Button("Sign out", type="submit", cls="text-button"), method="post", action="/auth/logout"),
                        cls="side-user",
                    ),
                    id="side-nav",
                    cls="sidebar",
                ),
                Div(
                    Header(
                        Div(Button("☰", type="button", cls="mobile-menu", data_action="toggle-nav", aria_label="Open navigation"), Div(Span("Workspace", cls="top-eyebrow"), H1(title)), cls="top-title"),
                        Div(A(icon("search"), Span("Search catalog"), href="/app/catalog", cls="top-search"), Span("Demo data" if settings().repository_mode=="demo" else "Connected data", cls="environment-badge"), cls="top-actions"),
                        cls="topbar",
                    ),
                    Main(*content, id="main-content", cls=f"workspace{' workspace-wide' if wide else ''}"),
                    cls="app-main",
                ),
                Div(cls="nav-scrim", data_action="toggle-nav"),
                cls="app-frame",
            ),
            cls="app-body",
        ),
        lang="en",
    )


def page_intro(eyebrow: str, heading: str, description: str, *actions):
    return Div(
        Div(Span(eyebrow, cls="eyebrow"), H2(heading), P(description)),
        Div(*actions, cls="page-actions") if actions else "",
        cls="page-intro",
    )


def metric_card(label: str, value, detail: str, tone: str = "blue"):
    return Article(Span(label, cls="metric-label"), Div(Span(str(value), cls="metric-value"), Span(cls=f"metric-pulse {tone}")), P(detail), cls="metric-card")


def status_badge(value: str):
    label = value.replace("_", " ").title()
    tone = "neutral"
    if value.lower() in {"certified", "passed", "healthy", "approved", "resolved", "full"}:
        tone = "good"
    elif value.lower() in {"failed", "error", "unhealthy", "rejected", "critical"}:
        tone = "bad"
    elif value.lower() in {"warning", "attention", "open", "waiting", "high"}:
        tone = "warn"
    elif value.lower() in {"verified", "in_progress", "contract-ready", "contract"}:
        tone = "info"
    return Span(Span(cls="status-dot"), label, cls=f"status-badge {tone}")


def platform_badge(platform: str):
    initials = {"Snowflake": "S", "Fabric": "F", "Databricks": "D"}.get(platform, platform[:1])
    return Span(Span(initials, cls=f"platform-icon {platform.lower()}"), platform, cls="platform-badge")


def score_ring(score: float, size: str = "normal"):
    tone = "good" if score >= 95 else "warn" if score >= 85 else "bad"
    return Div(Span(f"{score:.0f}"), Small("/100"), cls=f"score-ring {tone} {size}", style=f"--score:{max(0, min(100, score)) * 3.6}deg")


def asset_row(asset: Asset):
    return Tr(
        Td(A(Div(Strong(asset.name), Code(asset.qualified_name)), href=f"/app/assets/{asset.id}", cls="asset-link")),
        Td(platform_badge(asset.platform)),
        Td(asset.domain),
        Td(status_badge(asset.certification)),
        Td(Div(Span(style=f"width:{asset.quality_score}%"), cls="mini-bar"), Small(f"{asset.quality_score:.1f}%")),
        Td(Div(Strong(asset.owner.split("@")[0].replace(".", " ").title()), Small("Owner"), cls="person-cell")),
        Td(A(icon("arrow"), href=f"/app/assets/{asset.id}", cls="row-arrow", aria_label=f"Open {asset.name}")),
    )


def empty_state(title: str, description: str):
    return Div(Span("◇", cls="empty-icon"), H3(title), P(description), cls="empty-state")


def section_header(title: str, description: str = "", action=None):
    return Div(Div(H3(title), P(description) if description else ""), action or "", cls="section-header")


def tag_list(tags: list[str]):
    return Div(*[Span(tag, cls="tag") for tag in tags], cls="tag-list")
