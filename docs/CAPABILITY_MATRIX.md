# Adapter capability matrix

| Capability | Snowflake | Microsoft Fabric | Databricks | Demo/reference |
|---|---|---|---|---|
| Connection and health | Implemented | Contract-complete | Contract-complete | Implemented |
| Asset metadata | ACCOUNT_USAGE tables/views | Contract-complete for Fabric APIs/Purview integration | Contract-complete for Unity Catalog | Implemented |
| Fields | ACCOUNT_USAGE columns | Contract-complete | Contract-complete | Implemented |
| Table lineage | OBJECT_DEPENDENCIES | Contract-complete | Contract-complete | Implemented |
| Column/query lineage | ACCESS_HISTORY | Contract-complete | Contract-complete | Adapter contract supported |
| Tags/classifications | Read and guarded write-back | Contract-complete/read target | Contract-complete/read-write target | Implemented |
| Source grants | GRANTS_TO_ROLES plus identity alias mapping | Contract-complete | Contract-complete | Public demonstration grants |
| Usage | ACCESS_HISTORY rollups | Contract-complete | Contract-complete | Implemented |
| Quality SQL | Source execution with timeout and isolated role/warehouse | Contract-complete SQL/Spark target | Contract-complete SQL/Spark target | Deterministic execution |
| Incremental cursor | Implemented | Contract-defined | Contract-defined | Implemented |

“Contract-complete” means the common callable surface, capability declaration, configuration validation and explicit not-configured behavior are implemented and tested; tenant transport/API extraction awaits credentials and a deployment-specific implementation package. It never means live extraction was tested against a tenant.

Secondary adapters implement `PlatformAdapter` and are registered without core redesign. Candidate order: BigQuery, Redshift/Glue, Synapse/ADLS, Oracle, Teradata and SAP, prioritised by verified demand.
