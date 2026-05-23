"""Memory plane: backends, ops, results, registry.

Mirrors :mod:`rath.backend` for the recall/persist axis. ``rath.memory`` and
``rath.backend`` are independent — neither imports from the other. ``Agent``
holds both (memory store + sandbox) without coupling them.

Public surface lands as it ships; this initial revision only exposes the
:class:`MemoryOp` and :class:`MemoryResult` value-object families.
"""

from __future__ import annotations
