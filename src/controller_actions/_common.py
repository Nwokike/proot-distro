"""Shared helpers for the controller action mixins."""

from __future__ import annotations

from core import tokens
from core.constants import COMPRESS_EXT as _COMPRESS_EXT  # noqa: F401 - re-export


def _reason(exc: BaseException) -> str:
    """One honest line for a failure — never a bare swallow."""
    text = str(exc).strip() or exc.__class__.__name__
    return text.splitlines()[0][: tokens.ERROR_LINE_MAX_CHARS]
