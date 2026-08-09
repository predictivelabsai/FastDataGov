# Product roadmap

Roadmap ordering is evidence-led and carries no delivery commitment.

## Near term

- Tenant-verified Microsoft Fabric transport across OneLake, warehouse, lakehouse, semantic model and Purview evidence.
- Tenant-verified Databricks transport across Unity Catalog, system tables and SQL/Spark quality execution.
- dbt manifest/run-results enrichment and Power BI semantic lineage enrichment.
- Saved searches, bulk stewardship operations and configurable certification evidence checklists.

## Next adapters

BigQuery, Redshift/AWS Glue, Synapse/ADLS Gen2, then Oracle, Teradata and SAP based on demand and maintainership. Every adapter must pass the public contract, pagination/incremental, error, grant-visibility and fixture tests.

## Later extensions

Policy attestation packs, richer notification templates, open telemetry export, graph-optimised lineage projection, multilingual glossary and separately scoped AI/model-governance modules. MDM, ETL execution and source-native authorization remain intentional non-goals unless a future major design explicitly changes the boundary.
