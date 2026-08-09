# Personas and verified user journeys

## Data consumer or analyst

1. Sign in through Microsoft Entra ID, Google OpenID Connect, or local developer auth.
2. Search `/app/catalog` by technical name, meaning, term, tag, field or classification; refine by platform, domain, trust, sensitivity, owner and refresh window.
3. Inspect an asset’s business context, fields, source-aware visibility, quality, ownership, usage and evidence-backed lineage.
4. Inspect `/app/products` for reusable packages and service expectations.
5. Submit an access request; follow the decision in the stewardship queue.

## Data steward

1. Open assigned metadata and quality work in `/app/work`.
2. Add versioned business metadata and glossary links without overwriting adapter-owned technical metadata.
3. Define or revise quality expectations and queue an immediate run.
4. Add a confidence-labelled manual lineage edge where native evidence has a known gap.
5. Record discussion and resolve the work item, preserving status history and audit evidence.

## Data owner

1. Review quality, lineage, access guidance and usage for an asset or data product.
2. Decide certification, set expiry and record decision notes.
3. Approve or reject access and certification work.
4. Attest an owner/steward assignment with an expiry; renewal work is generated before expiry.

## Data engineer or platform administrator

1. Configure an adapter using non-secret JSON and an `env:` credential reference.
2. Test health, trigger sync and monitor durable jobs, attempts and errors.
3. Map corporate identities/groups to source-platform roles so imported grants govern discovery.
4. Investigate incremental sync, lineage, quality or notification failures through job and audit views.

## Governance lead

1. Maintain domain hierarchy, workflow due dates, approval roles and notification routing.
2. Review catalog/accountability/quality coverage, adoption and time-to-trusted-data measures.
3. Inspect the audit trail, overdue work, expiring attestations and certification renewal queues.
4. Use exported catalog/API data for governance reporting and improvement prioritisation.

The HTML routes above are the maintained wireframe references: the running product is the authoritative accessible, responsive wireframe.
