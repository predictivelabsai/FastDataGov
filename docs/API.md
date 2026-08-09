# API and export

Authenticated JSON endpoints are under `/api/v1`. They use the same identity, role checks and source-grant visibility as the web application. Responses use `{data, meta}`; catalog pagination accepts `page` and `page_size` (maximum 500).

Read endpoints cover assets, individual assets, lineage, impact analysis, quality, glossary, adapters, products, work, domains, audit, jobs and pilot metrics. `GET /api/v1/exports/assets` returns a source-filtered CSV attachment.

Role-checked JSON mutations create/update glossary terms and quality rules, create manual lineage, queue quality runs and add work comments. Browser/session clients must remain same-origin. This initial API intentionally does not issue long-lived bearer tokens; deployments needing service-to-service access should place a standards-based API gateway in front and map verified identity claims.

Errors use HTTP status codes and a short message; adapter/secret internals must not be exposed. Consumers should treat new response fields as backward-compatible and use the `api_version` metadata for major-version negotiation.
