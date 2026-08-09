from fastdatagov.adapters.base import AdapterCapabilities
from fastdatagov.adapters.contract_ready import ContractReadyAdapter


class FabricAdapter(ContractReadyAdapter):
    key = "fabric"
    display_name = "Microsoft Fabric"
    capabilities = AdapterCapabilities("contract", "contract", "contract", "read", "contract", "none", "contract")
    configuration_help = "Configure the Fabric tenant, API endpoint, workspace scope, and Entra service-principal credential reference."
