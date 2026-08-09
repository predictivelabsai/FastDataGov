from fastdatagov.adapters.base import AdapterCapabilities
from fastdatagov.adapters.contract_ready import ContractReadyAdapter


class DatabricksAdapter(ContractReadyAdapter):
    key = "databricks"
    display_name = "Databricks"
    capabilities = AdapterCapabilities("contract", "contract", "contract", "read/write", "contract", "contract", "contract")
    configuration_help = "Configure the workspace URL, Unity Catalog scope, SQL warehouse, and service-principal credential reference."
