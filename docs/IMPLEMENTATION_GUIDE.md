# Implementation guide

## 1. Discover and design

Inventory platforms, identities, network paths, source governance features, priority domains/products and existing lineage/quality tools. Agree ownership semantics, sensitivity taxonomy, workflow decisions, success measures and RACI. Keep customer-specific material outside the upstream repository.

## 2. Establish the platform

Deploy PostgreSQL 17+, the FastHTML web process, scheduler and one or more workers. Terminate TLS at the ingress, inject secrets through the deployment secret manager, apply append-only migrations and configure backups/observability. Production configuration validation requires configured Entra ID or Google OpenID Connect and a strong session secret.

## 3. Connect Snowflake

Use a least-privilege metadata role for ACCOUNT_USAGE and a separate quality role/warehouse with SELECT only on approved datasets. Use a separate optional write-back role for existing governance tags. Store only `env:` credential references. Configure corporate-to-source principal aliases before treating imported grants as an access decision.

## 4. Load and reconcile

Test health, queue sync, inspect job/sync counts and reconcile representative assets, fields, tags, grants, lineage and usage against Snowflake. Document ACCOUNT_USAGE latency and unsupported object types. Never convert absent evidence into invented lineage.

## 5. Configure governance

Create the domain hierarchy, glossary, data products, owner/steward assignments, quality rules, workflow due dates, notification channels and pilot baselines. Business metadata revisions are central; technical metadata remains adapter-owned.

## 6. Iterate and accept

Deliver short slices around complete persona journeys. Test authorization with ordinary and privileged identities. Capture performance, usability and data-reconciliation evidence. Track gaps in the completion matrix and local acceptance log.

## 7. Transition

Execute the operations runbook, backup/restore and failure drills. Train by role, transfer configuration ownership, agree support/escalation, complete hypercare and revoke implementation-only access.

## Assumptions and dependencies

- The deploying organisation supplies lawful access, connectivity and source privileges.
- Source APIs and account editions determine available evidence and latency.
- Business definitions, owners, access decisions and compliance interpretations remain organisational responsibilities.
- Fabric and Databricks are contract-complete until tenant implementations are installed and verified.
- FastDataGov orchestrates source capabilities; it does not replace ETL, MDM or source-native security engines.
