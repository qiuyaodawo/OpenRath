"""Persistent identity for sandboxes.

Today this means:

* **Local backend** — a stable working directory under
  ``.openrath/sandboxes/local/<uuid>/`` that survives ``close()``, so a
  resumed session can pick up where it left off without re-mkdtemping.
* **OpenSandbox backend** — a JSON record under
  ``.openrath/sandboxes/opensandbox/<uuid>.json`` pinning the remote
  ``native.id`` so a future reattach (Phase B) has the data it needs.

Public surface lives in :class:`PersistentSandboxRegistry`. Paths can be
resolved directly via the helpers in :mod:`rath.backend.persistence.paths`.
"""

from rath.backend.persistence.paths import (
    LOCAL_SUBDIR,
    OPENSANDBOX_INDEX_SUFFIX,
    OPENSANDBOX_SUBDIR,
    SANDBOXES_DIR_NAME,
    ensure_local_root,
    ensure_opensandbox_root,
    local_root,
    local_sandbox_dir,
    opensandbox_index_path,
    opensandbox_root,
    sandboxes_dir,
)
from rath.backend.persistence.registry import (
    PersistentSandboxRegistry,
    RemoteSandboxRecord,
)

__all__ = [
    # Registry
    "PersistentSandboxRegistry",
    "RemoteSandboxRecord",
    # Paths
    "SANDBOXES_DIR_NAME",
    "LOCAL_SUBDIR",
    "OPENSANDBOX_SUBDIR",
    "OPENSANDBOX_INDEX_SUFFIX",
    "sandboxes_dir",
    "local_root",
    "local_sandbox_dir",
    "opensandbox_root",
    "opensandbox_index_path",
    "ensure_local_root",
    "ensure_opensandbox_root",
]
