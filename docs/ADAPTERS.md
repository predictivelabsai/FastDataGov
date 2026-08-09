# Adapter development

All platforms implement `PlatformAdapter` in
`fastdatagov/adapters/base.py`. The contract deliberately separates raw source
access from persistence and workflow decisions.

## Required operations

| Operation | Purpose |
|---|---|
| `connect` / `close` | Establish and release the least-privilege platform session. |
| `health` | Validate connectivity and report a safe diagnostic. |
| `discover_assets` | Return platform objects and an incremental cursor. |
| `discover_fields` | Return fields for a bounded set of assets. |
| `discover_lineage` | Return evidence-labelled asset or field edges. |
| `discover_tags` | Surface platform classifications and tags. |
| `discover_usage` | Return bounded usage rollups, never raw query text. |
| `discover_grants` | Return source discovery principals and privileges. |
| `execute_quality` | Execute a validated rule close to the source data. |
| `write_tags` | Perform explicitly enabled, audited native tag write-back. |

Adapters publish an `AdapterCapabilities` manifest. Unsupported features must
be reported honestly rather than silently returning empty success.

## Cursor rules

- Cursors are opaque JSON owned by the adapter.
- Return a new cursor only after the returned page is complete.
- Watermarks must be overlap-safe; source timestamps are not assumed unique.
- A retry with the previous cursor must be idempotent.
- Extraction should upsert observations and never delete governance history.

## Credentials

`ConnectionConfig.credential_ref` identifies a deployment secret. It must not
contain the secret itself. The worker resolves the reference at execution time.
Do not log credentials, provider tokens, private keys, or raw queries that may
contain sensitive literals.

## Testing an adapter

Every adapter must remain instantiable and implement the complete contract.
Add tests for:

- configuration and health states;
- deterministic asset and field mapping;
- stable external identifiers;
- pagination and cursor replay;
- partial permission failures;
- lineage evidence and confidence;
- timeout and retry classification;
- unsafe quality expression rejection;
- write-back disabled and enabled paths.

Use the deterministic demo adapter as the behavioral reference. Live-provider
tests belong in a separately selected integration suite and must never be part
of the default offline test run.

## Custom Python quality packages

Trusted packages may publish a callable under the
`fastdatagov.quality_rules` Python entry-point group. The rule expression is
only the entry-point name; FastDataGov never evaluates stored source or imports
an arbitrary module path. The callable receives `(adapter, rule_spec)` and must
return `QualityResultRecord`. Operators review/install/package this code and
apply their own isolation and resource limits.

## Priority adapters

- **Snowflake:** live metadata/fields, dependency and ACCESS_HISTORY column
  lineage, transitive role grants, tags, usage, guarded SQL quality and tag
  write-back. ACCESS_HISTORY requires an eligible Snowflake edition and its
  documented evidence/retention limits apply. See Snowflake's
  [ACCESS_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/access_history)
  and [GRANTS_TO_ROLES](https://docs.snowflake.com/en/sql-reference/account-usage/grants_to_roles)
  references.
- **Microsoft Fabric:** complete contract and capability manifest; tenant
  transport is installed when workspace scope and service-principal access are
  available.
- **Databricks:** complete contract and capability manifest; tenant transport
  is installed when workspace, Unity Catalog, and SQL warehouse access are
  available.
