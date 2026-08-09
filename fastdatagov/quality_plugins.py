"""Safe extension point for installed custom Python quality rules."""

from __future__ import annotations

import re
from importlib.metadata import entry_points

from fastdatagov.adapters.base import AdapterError, PlatformAdapter, QualityResultRecord, QualityRuleSpec

ENTRY_POINT_NAME=re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,127}$")


def execute(adapter: PlatformAdapter, rule: QualityRuleSpec) -> QualityResultRecord:
    """Execute an explicitly installed `fastdatagov.quality_rules` entry point.

    The database stores only the entry-point name. It never stores or evaluates Python source.
    """
    name=rule.expression.strip()
    if not ENTRY_POINT_NAME.fullmatch(name): raise AdapterError("Custom Python expressions must be installed entry-point names")
    matches=[item for item in entry_points(group="fastdatagov.quality_rules") if item.name==name]
    if len(matches)!=1: raise AdapterError(f"Custom quality plugin is not installed: {name}")
    result=matches[0].load()(adapter,rule)
    if not isinstance(result,QualityResultRecord): raise AdapterError("Custom quality plugin returned an invalid result")
    return result
