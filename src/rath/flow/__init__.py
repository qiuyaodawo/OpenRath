"""Execution-flow namespace (torch-style package boundary).

Concrete tool-call types and functional factories live in :mod:`rath.flow.tool`.
This package intentionally does not re-export those symbols so there is a
single public home for ``FlowTool*`` names.
"""

from __future__ import annotations

__all__: list[str] = []
