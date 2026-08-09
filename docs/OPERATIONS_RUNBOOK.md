# Operations runbook

## Service topology

Run `web`, `scheduler`, one or more stateless `worker` processes and PostgreSQL. Only the web ingress is public. Workers require egress to configured platforms/notification endpoints; PostgreSQL remains private.

## Daily checks

- `/healthz` returns process health; `/readyz` confirms repository readiness.
- Review `/app/admin/jobs` for exhausted retries and `/app/admin/connections` for stale/unhealthy connections.
- Review notification failures, quality failures, overdue work and expiring certifications/attestations.
- Confirm database backup completion and monitoring coverage.

## Failure handling

1. Identify job kind, target, attempt count and sanitised error.
2. Correct credentials/network/permissions/configuration without placing secrets in the database.
3. Queue a health check before a new sync or quality run.
4. Preserve failed jobs, sync runs and audit events as evidence; do not delete them to make dashboards green.
5. Escalate source outages and business-rule disputes to their accountable owner.

Workers use `FOR UPDATE SKIP LOCKED`, bounded attempts and exponential delay. Notification delivery uses an outbox, HTTPS host allowlist and no redirects. Adapter sync is upsert/idempotent by connection/external ID; quality and audit records are append-only evidence.

## Backup and restore

Back up PostgreSQL with organisation-approved encrypted tooling and retention. Quarterly, restore into an isolated environment, apply any later migrations, compare row counts and exercise catalog, lineage and workflow reads. Secrets are restored from the secret manager, never from database backup. Record recovery point/time evidence.

## Upgrade and rollback

Build an immutable image, back up PostgreSQL, review append-only migrations, deploy scheduler/workers then web, and smoke-test. Application rollback may use the prior image only if its schema is forward-compatible; database migrations are not destructively reversed. Ship a corrective forward migration when needed.

## Privacy and retention

Audit, usage and identity metadata can be personal information. Define retention and subject-access handling locally. Restrict admin/audit roles, minimise imported query-user details and never store source credentials or query result data.
