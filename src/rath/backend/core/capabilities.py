"""Static capability description for a backend.

Capabilities are deliberately minimal in this phase. New fields should be added
only when an actual backend or scheduling decision needs them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IsolationLevel(str, Enum):
    """Isolation level offered by the backend's runtime."""

    PROCESS = "process"
    CONTAINER = "container"
    MICROVM = "microvm"
    VM = "vm"


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Static, backend-class-level capability description.

    Returned by :meth:`Backend.capabilities` as a classmethod, so the values
    must not depend on a specific instance or runtime probing.
    """

    isolation: IsolationLevel
    supports_command: bool
    supports_filesystem: bool
    supports_code_interpreter: bool
    cold_start_ms_p50: int | None = None
    max_sandboxes: int | None = None
