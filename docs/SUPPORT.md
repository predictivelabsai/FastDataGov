# Support model

FastDataGov is MIT-licensed community software. Public issue reports and pull requests follow `CONTRIBUTING.md` and security reports follow `SECURITY.md`; no response-time warranty is implied.

Deploying organisations can choose:

- Internal ownership: their platform/data practice owns deployment, upgrades and incidents.
- Partner-assisted support: an implementation partner provides agreed service hours, response targets and release assistance.
- Managed operation: an operator runs the application under a separate service agreement while business governance remains organisationally accountable.

Define local severity, support hours, response/restoration targets, on-call contacts, data residency, subcontractor access, maintenance windows and exit assistance. A sensible severity model is: S1 security or broad service loss; S2 major workflow/adapter degradation; S3 limited defect with workaround; S4 request/documentation.

Support bundles should contain version, timestamp/timezone, route/job/connection identifier, sanitised error and reproduction steps. Never attach credentials, tokens, raw restricted metadata or query results.
