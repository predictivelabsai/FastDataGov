# FastDataGov

FastDataGov is an open-source, business-friendly data governance platform built
with FastHTML, PostgreSQL, and Python. It provides a unified catalog, lineage,
data quality, stewardship, ownership, certification, and access-request
experience across connected data platforms.

The platform is deliberately vendor-neutral. Snowflake is the first fully
implemented adapter; Microsoft Fabric and Databricks implement the same public
contract and can be enabled without redesigning the core.

## What works

- Searchable catalog with platform, domain, trust, owner, and quality filters.
- Business glossary and asset-to-term relationships.
- Versioned business/field metadata, native and business tags, sensitivity,
  domain hierarchy and reusable data products.
- Asset detail pages with ownership, stewardship, sensitivity, freshness,
  quality, lineage, access guidance, and audit context.
- Interactive table- and column-aware lineage with impact views.
- Manual, dbt and generic lineage enrichment with explicit evidence labels.
- Versioned quality rules, run history, scores, alerts, and remediation work.
- Stewardship queues for quality remediation, certification, metadata
  enrichment, access requests, and ownership attestation.
- Adapter health, capability manifests, incremental sync cursors, and job runs.
- Configurable workflow due dates/approvals, comments/history, renewable asset
  and product certification, scoped accountability and notification outbox.
- Source-grant discovery with explicit identity-to-platform principal aliases.
- Microsoft Entra ID or Google production authentication and safe local developer auth.
- Paginated JSON API, directional impact API, dbt/generic lineage imports and
  source-filtered catalog CSV export.
- Deterministic demo data so the complete product is useful without cloud
  credentials.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# For live Snowflake work: pip install -e '.[dev,snowflake]'
cp .env.example .env
python main.py
```

Open <http://localhost:5062>. The checked-in example configuration uses local
developer authentication and the deterministic demo repository. Sign in with
any valid email address; no password or external identity call is made in this
mode.

## PostgreSQL mode

```bash
export DATABASE_URL=postgresql://fastdatagov:fastdatagov@localhost:5432/fastdatagov
export REPOSITORY_MODE=postgres
python -m fastdatagov.db.migrate
python -m fastdatagov.synthetic.seed
python main.py
```

All database objects live in the `fastdatagov` schema. Migrations are
append-only and recorded in `fastdatagov.schema_migrations`.

## Microsoft Entra ID

Set `AUTH_MODE=entra` and configure the variables documented in
[`.env.example`](.env.example). Register `/auth/callback` as the HTTPS redirect
URI. FastDataGov requests only OpenID identity scopes and stores no identity
provider access tokens in application tables.

## Google OpenID Connect

Set `AUTH_MODE=google`, configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
and the access-list variables documented in [`.env.example`](.env.example),
and register `/auth/google/callback` as the exact HTTPS redirect URI. State is
validated by the OAuth client, only `openid email profile` is requested, and
the returned email must be verified and permitted. Use
`GOVERNANCE_ADMIN_EMAILS` to bootstrap the first governance administrators.

## Commands

```bash
pytest -q                         # offline unit and application tests
python -m fastdatagov.db.migrate # apply pending PostgreSQL migrations
python -m fastdatagov.jobs.worker
python -m fastdatagov.jobs.scheduler
```

## FastSME Coolify deployment

FastDataGov is catalogued by the sibling FastDevOps control plane. With
deployment credentials in the ignored mode-`0600` `.env`, use:

```bash
python scripts/coolify.py validate
python scripts/coolify.py doctor
python scripts/coolify.py status
python scripts/coolify.py env --sync --yes
python scripts/coolify.py deploy --yes
```

The declared production target is `https://datagov.fastsme.com`, port `5062`,
PostgreSQL repository mode, `/healthz`, and Google OpenID Connect at
`/auth/google/callback`. Secret values remain in ignored files and Coolify.

See [architecture](docs/ARCHITECTURE.md), [adapter development](docs/ADAPTERS.md),
[API](docs/API.md), [implementation](docs/IMPLEMENTATION_GUIDE.md),
[pilot](docs/PILOT_RUNBOOK.md), [operations](docs/OPERATIONS_RUNBOOK.md),
[training and transition](docs/TRAINING_AND_TRANSITION.md),
[capability matrix](docs/CAPABILITY_MATRIX.md), [security](SECURITY.md), and
[contributing](CONTRIBUTING.md). The maintained functional release gate is
[docs/COMPLETION_MATRIX.md](docs/COMPLETION_MATRIX.md).

## License

MIT — see [LICENSE](LICENSE).
