"""OpenRath: a torch-like API framework for dynamic multi-agent workflow.

Public surfaces today are :mod:`rath.backend` (sandbox execution) and
:mod:`rath.flow.tool` (flow tool call value types and factories).
"""

from rath import backend
from rath import flow

__all__ = ["backend", "flow"]
