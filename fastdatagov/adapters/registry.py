from __future__ import annotations

from typing import Type

from fastdatagov.adapters.base import ConnectionConfig, PlatformAdapter
from fastdatagov.adapters.databricks import DatabricksAdapter
from fastdatagov.adapters.demo import DemoAdapter
from fastdatagov.adapters.fabric import FabricAdapter
from fastdatagov.adapters.snowflake import SnowflakeAdapter

adapter_registry: dict[str, Type[PlatformAdapter]] = {
    "demo": DemoAdapter,
    "snowflake": SnowflakeAdapter,
    "fabric": FabricAdapter,
    "databricks": DatabricksAdapter,
}


def build_adapter(adapter_type: str, connection: ConnectionConfig) -> PlatformAdapter:
    try:
        adapter_class = adapter_registry[adapter_type]
    except KeyError as exc:
        raise ValueError(f"Unknown adapter type: {adapter_type}") from exc
    return adapter_class(connection)
