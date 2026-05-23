"""Static guard: :mod:`rath.memory` must not import from :mod:`rath.backend`.

The memory plane and sandbox plane are deliberately parallel and independent.
Any ``from rath.backend …`` or ``import rath.backend`` inside ``rath/memory/``
(excluding ``adapters/``, where third-party adapters may bridge the two) is
a regression.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import rath.memory


_MEMORY_ROOT = Path(rath.memory.__file__).parent


def _python_files() -> list[Path]:
    files = [
        p
        for p in _MEMORY_ROOT.rglob("*.py")
        if "adapters" not in p.relative_to(_MEMORY_ROOT).parts
    ]
    assert files, "expected to find python files under rath/memory/"
    return files


def test_no_from_rath_backend_imports():
    offenders: list[tuple[Path, int, str]] = []
    for path in _python_files():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("from rath.backend"):
                offenders.append((path, i, line))
            if stripped.startswith("import rath.backend"):
                offenders.append((path, i, line))
    assert not offenders, f"forbidden cross-imports: {offenders!r}"


def test_rath_memory_exposes_public_api():
    expected = {
        "MemoryBackend",
        "MemoryStore",
        "MemoryStoreSpec",
        "MemoryCapabilities",
        "ScopeModel",
        "MemoryOp",
        "MemoryOpWrite",
        "MemoryOpRead",
        "MemoryOpList",
        "MemoryOpTree",
        "MemoryOpFind",
        "MemoryOpSearch",
        "MemoryOpResource",
        "MemoryOpCommit",
        "MemoryResult",
        "MemoryHit",
        "MemoryEntry",
        "MemoryFindResult",
        "MemoryReadResult",
        "MemoryListResult",
        "MemoryWriteResult",
        "MemoryCommitResult",
        "MemoryExecutionFailure",
        "MemoryBackendError",
        "MemoryBackendNotFound",
        "MemoryStoreClosed",
        "UnsupportedMemoryOp",
        "MemoryNotFound",
        "MemoryConflict",
        "register",
        "list_names",
        "get",
        "get_class",
        "is_available",
        "preferred",
        "set_default",
        "current",
    }
    missing = expected - set(dir(rath.memory))
    assert not missing, f"missing public exports: {sorted(missing)}"


def test_rath_memory_has_no_default_registered_backends():
    """Importing :mod:`rath.memory` in a fresh interpreter must not register
    adapters; the OpenViking adapter is gated behind the optional extra and
    must only register when explicitly imported."""
    script = textwrap.dedent(
        """
        import rath.memory
        names = rath.memory.list_names()
        assert names == [], f"unexpected default backends: {names!r}"
        print("OK")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_rath_top_level_exposes_memory_submodule():
    import rath

    assert hasattr(rath, "memory")
    # And `memory` is in __all__ alongside the other planes.
    assert "memory" in rath.__all__
