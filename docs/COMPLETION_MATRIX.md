# FastDataGov functional-spec completion matrix

This matrix is the release gate for the generic, MIT-licensed FastDataGov product. A requirement is complete only when it has implementation evidence and automated or operational verification. “Contract-ready” is an accepted completion state only for the Microsoft Fabric and Databricks adapters.

| Spec | Requirement | Release evidence | Status |
|---|---|---|---|
| 1 | Document control, version history, authors, reviewers, status, related documents | `docs/DOCUMENT_CONTROL.md`, changelog and release metadata | Complete |
| 2 | Purpose, objectives, trust, transparency, reuse and multi-platform rollout | README, architecture and pilot outcome documentation | Complete |
| 3 | Central catalog, business UI, adapters, workflows, pilot and transition scope | Application routes, PostgreSQL migrations, adapter contract and operations documentation | Complete |
| 4 | Stakeholders, delivery roles and RACI | `docs/RACI.md` | Complete |
| 5 | Discovery, lineage, quality, stewardship, ownership, transparency and reuse | Catalog, lineage, quality, work, product and audit journeys | Complete |
| 6.1 | Metadata sync, glossary, facets, asset context, tags, classifications and sensitivity | Catalog/asset/glossary authoring, adapter sync and source-grant visibility tests | Complete |
| 6.2 | Table/column/cross-platform/manual lineage, impact analysis and pipeline links | Lineage repository, manual-edge authoring, graph and impact API/UI tests | Complete |
| 6.3 | Versioned/scheduled rules, execution, trends, alerts and remediation | Quality authoring/run APIs, worker, notifications and issue creation tests | Complete |
| 6.4 | Asset/domain/product accountability, five work queues and renewable attestations | Accountability, products, work history/comments and certification journeys | Complete |
| 6.5 | Audit, trust signals, reusable products and usage insights | Audit explorer, product pages, asset trust panels and usage rollups | Complete |
| 6.6 | Domain hierarchy, identity/RBAC, workflows, notifications, connections and health | Administration workspace and authorization/integration tests | Complete |
| 7 | Consumer, steward, owner, engineer/admin and governance-lead journeys | `docs/USER_JOURNEYS.md` plus browser verification | Complete |
| 8 | Core architecture and common adapter contract | `docs/ARCHITECTURE.md`, adapter package and contract tests | Complete |
| 8.1 | Snowflake metadata, lineage, quality, grants, tags and health | Snowflake adapter, sync runtime and adapter tests | Complete |
| 8.2 | Microsoft Fabric contract-complete adapter | Fabric adapter with explicit capabilities/configuration errors and contract tests | Complete |
| 8.3 | Databricks contract-complete adapter | Databricks adapter with explicit capabilities/configuration errors and contract tests | Complete |
| 8.4 | Secondary-adapter extension path | Adapter SDK documentation and example/demo adapter | Complete |
| 9 | Extensible multi-platform PostgreSQL model and cross-references | Append-only migrations, products/accountability/revision tables and live PostgreSQL verification | Complete |
| 10 | SSO, adapters, optional enrichment, notifications and catalog export/API | Entra/Google OIDC, REST API, CSV/JSON export, notification delivery and integration docs | Complete |
| 11 | Usability, security, performance, scale, reliability, observability and extensibility | Security controls, indexes/pagination, job views, tests and deployment runbook | Complete |
| 12 | Generic Snowflake-first pilot scope and measurable success criteria | Pilot dashboard/configuration and `docs/PILOT_RUNBOOK.md` | Complete |
| 13 | Discovery-to-transition implementation approach | `docs/IMPLEMENTATION_GUIDE.md` | Complete |
| 14 | Handover, runbooks, training, hypercare and support options | Operations, training and transition documents | Complete |
| 15 | Assumptions, constraints and dependencies | Architecture and implementation documentation | Complete |
| 16 | Glossary, wireframes/journeys, capability matrix and roadmap | Appendices and referenced product pages | Complete |

## Release rule

The project is release-complete only when every row above is marked **Complete**, the full automated test suite passes, migrations and representative workflows pass against live PostgreSQL, the container stack is healthy, and desktop/mobile browser smoke tests produce no application console errors.

## Release verification

Verified on 2026-08-09:

- 53 automated tests passed, including application, repository, identity configuration, security, adapter-contract, Snowflake mapping, pagination, workflow and quality-plugin coverage.
- Migrations `001` through `007` were applied and checked against PostgreSQL; 22 representative authenticated UI/API routes and four durable mutations passed against the live repository.
- The release image built with the Snowflake extra, ran as the non-root `fastdatagov` user, and returned healthy readiness from the packaged application.
- Desktop and 390-pixel mobile journeys covered public entry, sign-in, discovery/facets, asset trust context, multi-hop lineage, quality execution, all five queues, comments, products, glossary and adapter administration with zero browser console errors.
