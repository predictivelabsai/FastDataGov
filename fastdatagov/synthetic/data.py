from __future__ import annotations

from fastdatagov.models import (
    AdapterStatus,
    Asset,
    AssetField,
    AuditEvent,
    GlossaryTerm,
    LineageEdge,
    QualityRule,
    WorkItem,
)


def _fields(*items: tuple[str, str, str, str]) -> list[AssetField]:
    return [AssetField(name, data_type, description, classification) for name, data_type, description, classification in items]


ASSETS = [
    Asset(1, "Customer", "PROD.CORE.CUSTOMER", "table", "Snowflake", "Customer", "Canonical customer records used across commercial analytics.", "One current record per customer organisation, including lifecycle and segment.", "alex.owner@example.com", "sam.steward@example.com", "confidential", "certified", 98.4, 97.0, "12 min ago", "Request the ANALYST_CORE role through the access workflow.", ["gold", "customer-360", "pii"], ["Customer", "Active customer"], _fields(("CUSTOMER_ID", "NUMBER", "Stable customer identifier", "identifier"), ("LEGAL_NAME", "VARCHAR", "Registered or trading name", "confidential"), ("SEGMENT", "VARCHAR", "Commercial segment", "internal"), ("STATUS", "VARCHAR", "Current lifecycle status", "internal")), 1842),
    Asset(2, "Sales order", "PROD.COMMERCIAL.SALES_ORDER", "table", "Snowflake", "Commercial", "Order headers from all direct and partner channels.", "A confirmed request for products or services, valued in the transaction currency.", "mia.owner@example.com", "lee.steward@example.com", "internal", "certified", 96.1, 95.0, "18 min ago", "Request the COMMERCIAL_READER role.", ["gold", "revenue"], ["Sales order", "Net revenue"], _fields(("ORDER_ID", "NUMBER", "Stable order identifier", "identifier"), ("CUSTOMER_ID", "NUMBER", "Ordering customer", "identifier"), ("ORDER_DATE", "DATE", "Date accepted", "internal"), ("NET_AMOUNT", "NUMBER(18,2)", "Net amount before tax", "financial")), 1331),
    Asset(3, "Invoice", "PROD.FINANCE.INVOICE", "table", "Snowflake", "Finance", "Issued and credited customer invoices.", "The governed finance view of customer invoices and settlement status.", "noah.owner@example.com", "ivy.steward@example.com", "confidential", "certified", 94.2, 93.0, "22 min ago", "Finance approval is required.", ["finance", "sox"], ["Invoice", "Net revenue"], _fields(("INVOICE_ID", "NUMBER", "Invoice identifier", "identifier"), ("ORDER_ID", "NUMBER", "Originating order", "identifier"), ("TOTAL_AMOUNT", "NUMBER(18,2)", "Invoice total", "financial"), ("PAID_AT", "TIMESTAMP_TZ", "Settlement timestamp", "financial")), 998),
    Asset(4, "Daily revenue", "ANALYTICS.FINANCE.DAILY_REVENUE", "view", "Snowflake", "Finance", "Daily recognised revenue by product and channel.", "Certified metric-ready revenue dataset for reporting and forecasting.", "noah.owner@example.com", "ivy.steward@example.com", "internal", "certified", 99.1, 98.0, "24 min ago", "Available to all finance analysts.", ["gold", "metric-ready"], ["Net revenue"], _fields(("REVENUE_DATE", "DATE", "Recognition date", "internal"), ("PRODUCT_LINE", "VARCHAR", "Product grouping", "internal"), ("NET_REVENUE", "NUMBER(18,2)", "Recognised net revenue", "financial")), 2788),
    Asset(5, "Product", "PROD.CORE.PRODUCT", "table", "Snowflake", "Product", "Current sellable product catalogue.", "Products and services approved for commercial use.", "zoe.owner@example.com", "sam.steward@example.com", "internal", "verified", 91.5, 89.0, "15 min ago", "Available through the CORE_READER role.", ["reference"], ["Product"], _fields(("PRODUCT_ID", "NUMBER", "Stable product identifier", "identifier"), ("PRODUCT_NAME", "VARCHAR", "Display name", "public"), ("ACTIVE_FLAG", "BOOLEAN", "Available for sale", "internal")), 744),
    Asset(6, "Support case", "PROD.SERVICE.SUPPORT_CASE", "table", "Snowflake", "Customer", "Customer service interactions and resolution outcomes.", "A request for help raised by or for a customer.", "alex.owner@example.com", "rory.steward@example.com", "restricted", "uncertified", 78.0, 72.0, "2 hr ago", "Customer Operations approval and privacy training required.", ["pii", "service"], ["Customer", "Support case"], _fields(("CASE_ID", "NUMBER", "Case identifier", "identifier"), ("CUSTOMER_ID", "NUMBER", "Affected customer", "identifier"), ("SUBJECT", "VARCHAR", "Issue summary", "confidential"), ("BODY", "VARCHAR", "Free-form case detail", "restricted")), 322),
    Asset(7, "Customer 360", "ANALYTICS.CUSTOMER.CUSTOMER_360", "dynamic_table", "Snowflake", "Customer", "Reusable customer profile combining commercial and service signals.", "The approved analytical view of the customer relationship.", "alex.owner@example.com", "sam.steward@example.com", "confidential", "verified", 88.8, 87.0, "35 min ago", "Request CUSTOMER_ANALYTICS with a documented use case.", ["data-product", "customer-360"], ["Customer", "Active customer"], _fields(("CUSTOMER_ID", "NUMBER", "Stable customer identifier", "identifier"), ("LIFETIME_VALUE", "NUMBER(18,2)", "Modelled customer value", "financial"), ("OPEN_CASES", "NUMBER", "Current unresolved cases", "internal")), 1065),
    Asset(8, "Order ingestion", "FABRIC/Commercial/order_ingestion", "pipeline", "Fabric", "Commercial", "Loads operational orders into the governed lakehouse zone.", "Technical pipeline providing order data to analytics products.", "mia.owner@example.com", "devon.steward@example.com", "internal", "verified", 93.0, 88.0, "41 min ago", "Visible to Fabric workspace members.", ["pipeline"], ["Sales order"], [], 92),
    Asset(9, "Commercial lakehouse orders", "FABRIC/CommercialLakehouse/Tables/orders", "delta_table", "Fabric", "Commercial", "Curated OneLake order dataset.", "Fabric representation of accepted sales orders.", "mia.owner@example.com", "lee.steward@example.com", "internal", "uncertified", 89.3, 82.0, "44 min ago", "Request access to the Commercial workspace.", ["onelake"], ["Sales order"], _fields(("order_id", "long", "Stable order identifier", "identifier"), ("customer_id", "long", "Ordering customer", "identifier"), ("net_amount", "decimal(18,2)", "Net order amount", "financial")), 178),
    Asset(10, "Customer feature table", "main.ml.customer_features", "delta_table", "Databricks", "Customer", "Curated behavioural features for customer analytics.", "Reusable customer characteristics with documented refresh and quality expectations.", "alex.owner@example.com", "sam.steward@example.com", "confidential", "uncertified", 84.6, 80.0, "1 hr ago", "Request USE CATALOG and SELECT through Unity Catalog.", ["unity-catalog", "feature"], ["Customer"], _fields(("customer_id", "BIGINT", "Stable customer identifier", "identifier"), ("orders_90d", "BIGINT", "Orders in trailing 90 days", "internal"), ("value_90d", "DECIMAL(18,2)", "Net value in trailing 90 days", "financial")), 286),
    Asset(11, "Finance semantic model", "FABRIC/Finance/Revenue Model", "semantic_model", "Fabric", "Finance", "Certified Power BI semantic model for revenue reporting.", "Measures and dimensions used for executive revenue reporting.", "noah.owner@example.com", "ivy.steward@example.com", "internal", "verified", 97.2, 94.0, "52 min ago", "Available through the Finance reporting workspace.", ["power-bi", "semantic-model"], ["Net revenue"], [], 1560),
    Asset(12, "Customer value job", "main.analytics.customer_value_job", "job", "Databricks", "Customer", "Produces customer lifetime value and engagement features.", "Scheduled transformation feeding the reusable customer profile.", "alex.owner@example.com", "devon.steward@example.com", "internal", "uncertified", 86.0, 79.0, "1 hr ago", "Visible to analytics engineering.", ["workflow"], ["Customer"], [], 61),
]

LINEAGE = [
    LineageEdge(1, 1, 2, "lookup", "query_history", 0.98),
    LineageEdge(2, 2, 3, "billing", "native", 1.0),
    LineageEdge(3, 3, 4, "aggregate", "query_history", 0.96),
    LineageEdge(4, 5, 4, "group by product", "query_history", 0.94),
    LineageEdge(5, 1, 7, "profile join", "query_history", 0.98),
    LineageEdge(6, 6, 7, "case metrics", "query_history", 0.91),
    LineageEdge(7, 2, 8, "extract", "manual", 0.72),
    LineageEdge(8, 8, 9, "load", "native", 1.0),
    LineageEdge(9, 1, 12, "feature input", "manual", 0.75),
    LineageEdge(10, 12, 10, "feature write", "native", 1.0),
    LineageEdge(11, 4, 11, "semantic import", "native", 1.0),
]

QUALITY_RULES = [
    QualityRule(1, 1, "Customer identifier is complete", "completeness", "passed", 100.0, "critical", "hourly", "12 min ago", "CUSTOMER_ID IS NOT NULL", [100, 100, 99.9, 100, 100, 100, 100]),
    QualityRule(2, 1, "Customer identifier is unique", "uniqueness", "passed", 99.9, "critical", "daily", "24 min ago", "COUNT(*) = COUNT(DISTINCT CUSTOMER_ID)", [99.8, 99.9, 99.9, 100, 99.9, 99.9, 99.9]),
    QualityRule(3, 2, "Order amount is valid", "validity", "passed", 98.6, "high", "hourly", "18 min ago", "NET_AMOUNT >= 0", [98.2, 98.4, 98.7, 98.5, 98.6, 98.6, 98.6]),
    QualityRule(4, 3, "Every invoice has an order", "consistency", "failed", 94.2, "high", "daily", "24 min ago", "ORDER_ID IN SALES_ORDER", [98, 97, 96, 96, 95, 94.8, 94.2]),
    QualityRule(5, 4, "Revenue is fresh", "freshness", "passed", 100.0, "critical", "hourly", "24 min ago", "MAX(REVENUE_DATE) >= CURRENT_DATE - 1", [100, 100, 100, 100, 100, 100, 100]),
    QualityRule(6, 6, "Case subject is populated", "completeness", "failed", 78.0, "medium", "daily", "2 hr ago", "SUBJECT IS NOT NULL", [85, 84, 83, 82, 80, 79, 78]),
    QualityRule(7, 7, "Customer profile is fresh", "freshness", "warning", 88.8, "high", "hourly", "35 min ago", "UPDATED_AT >= CURRENT_TIMESTAMP - INTERVAL '2 hours'", [93, 92, 91, 90, 89, 89, 88.8]),
    QualityRule(8, 9, "Fabric order identifiers are complete", "completeness", "passed", 99.2, "high", "daily", "44 min ago", "order_id IS NOT NULL", [98.8, 99, 99.1, 99.1, 99.2, 99.2, 99.2]),
]

WORK_ITEMS = [
    WorkItem(1, "quality", 3, "Investigate unmatched invoice orders", "open", "high", "ivy.steward@example.com", "Today", "Thirty-one invoice rows no longer resolve to an order."),
    WorkItem(2, "certification", 7, "Certify Customer 360 data product", "in_progress", "high", "alex.owner@example.com", "Tomorrow", "Review ownership, quality, lineage, and access guidance."),
    WorkItem(3, "metadata", 6, "Add business description for case body", "open", "medium", "rory.steward@example.com", "In 3 days", "Clarify permitted uses and retention context."),
    WorkItem(4, "access", 1, "Access request for Customer", "waiting", "medium", "alex.owner@example.com", "Today", "Analyst requests discovery and SELECT access for service reporting."),
    WorkItem(5, "attestation", 2, "Renew Sales order ownership", "open", "high", "mia.owner@example.com", "In 5 days", "Annual owner attestation expires shortly."),
    WorkItem(6, "quality", 6, "Resolve missing support case subjects", "in_progress", "medium", "rory.steward@example.com", "Tomorrow", "Completeness fell below the agreed threshold."),
    WorkItem(7, "certification", 9, "Review Fabric orders for certification", "open", "low", "mia.owner@example.com", "Next week", "Confirm source alignment and steward assignment."),
]

GLOSSARY = [
    GlossaryTerm(1, "Customer", "A person or organisation with a current or historical commercial relationship.", "Customer", "alex.owner@example.com", "approved", 4),
    GlossaryTerm(2, "Active customer", "A customer with an open contract or recognised activity in the previous 12 months.", "Customer", "alex.owner@example.com", "approved", 2),
    GlossaryTerm(3, "Sales order", "A confirmed request for products or services that has passed commercial validation.", "Commercial", "mia.owner@example.com", "approved", 3),
    GlossaryTerm(4, "Net revenue", "Recognised revenue after credits, discounts, and returns, excluding indirect tax.", "Finance", "noah.owner@example.com", "approved", 3),
    GlossaryTerm(5, "Data product", "A reusable, owned data asset with defined consumers, service expectations, and trust signals.", "Governance", "governance@example.com", "draft", 1),
    GlossaryTerm(6, "Invoice", "A formal request for payment issued for fulfilled products or services.", "Finance", "noah.owner@example.com", "approved", 1),
    GlossaryTerm(7, "Product", "A product or service approved for commercial use and governed reporting.", "Product", "zoe.owner@example.com", "approved", 2),
    GlossaryTerm(8, "Support case", "A request for assistance raised by or on behalf of a customer.", "Customer", "alex.owner@example.com", "approved", 1),
]

ADAPTERS = [
    AdapterStatus("snowflake", "Snowflake production", "healthy", "12 minutes ago", 7, "99.9%", {"metadata": "full", "lineage": "full", "quality": "full", "tags": "read/write", "usage": "full"}),
    AdapterStatus("fabric", "Microsoft Fabric", "contract-ready", "41 minutes ago", 3, "Ready", {"metadata": "contract", "lineage": "contract", "quality": "contract", "tags": "read", "usage": "contract"}, "Configure Fabric API credentials to enable live extraction."),
    AdapterStatus("databricks", "Databricks", "contract-ready", "1 hour ago", 2, "Ready", {"metadata": "contract", "lineage": "contract", "quality": "contract", "tags": "read/write", "usage": "contract"}, "Configure a Unity Catalog service principal to enable live extraction."),
]

AUDIT = [
    AuditEvent(1, "sam.steward@example.com", "updated metadata", "Customer", "8 minutes ago", "Added business context and linked glossary terms."),
    AuditEvent(2, "snowflake-adapter", "completed sync", "Snowflake production", "12 minutes ago", "7 assets, 24 fields, and 8 lineage edges observed."),
    AuditEvent(3, "ivy.steward@example.com", "opened quality issue", "Invoice", "24 minutes ago", "Consistency score crossed the 95% threshold."),
    AuditEvent(4, "alex.owner@example.com", "approved access", "Customer", "37 minutes ago", "Approved time-limited analyst access."),
    AuditEvent(5, "mia.owner@example.com", "attested ownership", "Sales order", "Yesterday", "Ownership renewed for twelve months."),
]
