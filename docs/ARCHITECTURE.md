# Architecture

FastDataGov is a modular monolith with three independently runnable process
types. They share a Python package and PostgreSQL schema while keeping request
latency separate from platform work.

```text
Browser
  └── FastHTML web process
        ├── discovery, lineage, quality, workflows, glossary
        ├── Entra ID / Google OIDC / developer auth
        └── authenticated JSON API
              │
        PostgreSQL (`fastdatagov` schema)
              │
        ┌─────┴────────┐
        │              │
   scheduler        workers
                       └── adapter registry
                             ├── Snowflake
                             ├── Microsoft Fabric
                             ├── Databricks
                             └── deterministic demo
```

## Design decisions

### Server-rendered hypermedia

FastHTML renders complete, accessible pages and small workflow fragments. Forms
continue to work without JavaScript. A tiny local script adds progressive
fragment replacement and lineage connectors; there is no frontend build chain
or third-party CDN dependency.

### PostgreSQL is the governance record

Normalised tables hold identities, assets, fields, terms, lineage, quality,
work, certifications, usage, visibility, and immutable audit events. JSONB is
reserved for native platform attributes, cursors, and evidence—not primary
business relationships.

### Stable asset identity

An asset is unique by `(connection_id, external_id)`. Adapters choose an
immutable provider identifier when available; otherwise the qualified name is
the documented fallback. Sync never hard-deletes governance history, and a
later observation clears an existing soft-delete marker.

### Source-aware discovery

`asset_visibility` stores imported user or group grants. `principal_aliases`
maps identity-provider identifiers to source roles when identity namespaces differ. Ordinary identities
may discover an asset only when no visibility rows exist for it or a matching
principal has a discover grant. Governance leads and administrators can see
the complete governance record.

### Durable platform work

The scheduler adds jobs to PostgreSQL. Workers claim jobs using
`FOR UPDATE SKIP LOCKED`, retry transient failures with bounded backoff, and
record sync outcomes. Web requests never wait for cloud platform extraction.

### Evidence-labelled lineage

Every edge identifies its evidence as `native`, `query_history`, `inferred`, or
`manual`, together with confidence and supporting attributes. The UI never
presents inferred or manually entered lineage as native fact.

### Guarded quality execution

The initial Snowflake implementation accepts validated row predicates and
builds a bounded aggregate query. Identifiers are constrained, mutating SQL and
multiple statements are rejected, a statement timeout is applied, and the
adapter is expected to use a dedicated read-only role and warehouse.

Custom Python is never stored or evaluated. A rule may name a package entry
point from `fastdatagov.quality_rules`; only code installed and trusted by the
operator can execute, and it must return the typed result contract. Untrusted
user Python requires an external isolated runner and is unsupported.

## Deployment

The included Compose topology runs PostgreSQL, web, worker, and scheduler
services. Production environments should provide:

- HTTPS termination and trusted forwarded headers;
- Microsoft Entra ID or Google OpenID Connect application registration;
- a random application secret from a secret manager;
- credential references injected only into workers;
- database backups and point-in-time recovery;
- outbound network restrictions per adapter endpoint;
- central logs, metrics, and alerts.

Startup validates that production uses a strong session secret and a configured
Entra ID or Google provider. Security headers, same-site sessions, secure production cookies, and
same-origin mutation checks are enabled in the web process.
