"""Decode raw bytes from host shells and subprocesses (encoding-safe)."""

from __future__ import annotations

import locale
import sys


def decode_subprocess_output(data: bytes) -> str:
    """Turn captured ``stdout``/``stderr`` bytes into text.

    Tries UTF-8 first (strict). On failure, uses the process locale and on Windows
    ``mbcs`` (ANSI/OEM code page) so ``cmd.exe`` / PowerShell output matches the
    console (e.g. GBK/cp936) instead of mojibake from forcing ``utf-8`` with
    ``errors="replace"``.
    """

    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    pref = locale.getpreferredencoding(False)
    if pref:
        try:
            return data.decode(pref, errors="replace")
        except LookupError:
            pass
    if sys.platform == "win32":
        try:
            return data.decode("mbcs", errors="replace")
        except LookupError:
            pass
    return data.decode("latin-1", errors="replace")


__all__ = ["decode_subprocess_output"]
