import pytest

from fastdatagov.adapters.base import AdapterError, ConnectionConfig, QualityRuleSpec
from fastdatagov.adapters.demo import DemoAdapter
from fastdatagov.quality_plugins import execute


def test_custom_python_quality_never_evaluates_source_or_module_paths():
    adapter=DemoAdapter(ConnectionConfig("demo","Demo",{}))
    with pytest.raises(AdapterError,match="entry-point names"):
        execute(adapter,QualityRuleSpec("1","custom_python","__import__('os').system('id')",95))
    with pytest.raises(AdapterError,match="not installed"):
        execute(adapter,QualityRuleSpec("1","custom_python","not-installed",95))
