# Generic Snowflake-first pilot runbook

## Default scope

- One production-like Snowflake connection using a metadata reader role.
- A dedicated quality execution role and warehouse, and an optional tightly scoped tag write-back role.
- Two business domains, two reusable data products and a representative mixture of tables/views.
- Named owners and stewards; all five workflow types exercised.
- Fabric and Databricks contract/readiness demonstration without claiming live tenant coverage.

## Entry criteria

- Approved network path and `env:` secret injection.
- Snowflake ACCOUNT_USAGE retention/latency understood.
- Entra ID or Google OpenID Connect registration and required identity identifiers available.
- Priority asset list, glossary seed, owner/steward roster and permitted quality workloads agreed.
- Baseline measures captured before enablement.

## Execution

1. Deploy PostgreSQL, web, scheduler and worker; apply migrations.
2. Configure the selected identity provider, role bindings and source-principal aliases.
3. Configure Snowflake metadata, quality and optional write-back roles; test health.
4. Run initial sync; reconcile asset/field/grant/lineage/usage counts with source evidence.
5. Seed business terms, descriptions, products, accountability and quality rules.
6. Exercise discovery, impact, failure remediation, access, certification and attestation journeys.
7. Run weekly feedback/reconciliation and correct configuration or operating-model gaps.
8. Complete security, operations, performance, recovery and handover gates.

## Default success measures

| Measure | Default target | Evidence |
|---|---:|---|
| Priority catalog coverage | ≥90% | `/app/admin/pilot`, source reconciliation |
| Owner and steward completeness | ≥90% | Pilot metric and assignment report |
| Critical-asset quality rule coverage | ≥75% | Quality dashboard |
| Median time to trusted data | ≤8 hours | Access/certification workflow timestamps |
| Weekly active users | ≥20 | Auth/audit rollup |
| Representative user satisfaction | ≥4/5 | Pilot survey outside the application |

Targets are configurable decisions, not product guarantees. Exit requires accepted gaps, named day-two owners, tested backup/restore, no unresolved critical security issue, and signed operational handover in the deploying organisation’s change system.
