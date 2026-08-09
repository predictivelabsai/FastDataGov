# Security policy

Please report suspected vulnerabilities privately to
`security@predictivelabs.ai`. Do not include customer metadata, credentials, or
exploit details in a public issue.

## Supported versions

Security fixes are applied to the latest release on the default branch during
the initial development period.

## Security model

- Production authentication uses Microsoft Entra ID or Google with OpenID Connect.
- Asset discovery can mirror source-platform user and group grants.
- Explicit aliases map corporate identity IDs to imported platform principals.
- Governance administration is role restricted.
- Sessions are signed, same-site, and HTTPS-only in production.
- Mutating browser requests are rejected when their origin is cross-site.
- Platform credentials are runtime secret references available to workers,
  never values stored in governance tables.
- Adapters use dedicated least-privilege identities.
- Quality rules run with statement timeouts and reject mutating SQL.
- Custom Python rules reference operator-installed entry points; source code is
  never accepted or evaluated from the database or UI.
- Webhook notifications require HTTPS, an explicit hostname allowlist, secret
  references, no redirects, durable retry and auditable terminal failure.
- Governance mutations and adapter runs create audit evidence.
- Pages set a restrictive content security policy and load no third-party
  frontend resources.

## Deployment responsibilities

Operators must configure HTTPS, rotate secrets, restrict database and outbound
network access, back up PostgreSQL, review imported visibility, and monitor job
failures. The default developer authentication mode must not be enabled in a
production environment; application startup rejects that configuration.
