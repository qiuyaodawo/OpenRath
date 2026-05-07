"""Project ``.env`` discovery and minimal parsing (shared utilities)."""

from __future__ import annotations

from pathlib import Path


def project_root_with_pyproject() -> Path:
    """Repository root: parent of ``src`` that contains ``pyproject.toml``."""
    return Path(__file__).resolve().parents[3]


def default_env_file_path() -> Path:
    """Default path: ``<project_root>/.env``."""
    return project_root_with_pyproject() / ".env"


def load_dotenv_if_present(
    path: Path | None = None,
    *,
    override: bool = False,
) -> bool:
    """Load a dotenv file when it exists.

    Returns ``True`` if the file was found and loaded.
    """
    from dotenv import load_dotenv

    p = path if path is not None else default_env_file_path()
    if p.is_file():
        load_dotenv(p, override=override)
        return True
    return False


def read_dotenv_value(env_path: Path, key: str) -> str | None:
    """Read a single ``KEY=value`` from a dotenv file (tests and diagnostics).

    Does not expand variable substitution. Skips comments and blank lines.
    """
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return None
    prefix = f"{key}="
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(prefix):
            raw = stripped[len(prefix) :].strip()
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
                return raw[1:-1]
            return raw
    return None
