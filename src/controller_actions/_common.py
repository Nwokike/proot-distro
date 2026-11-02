"""Shared helpers for the controller action mixins."""

from __future__ import annotations


def _reason(exc: BaseException) -> str:
    """One honest line for a failure — never a bare swallow."""
    text = str(exc).strip() or exc.__class__.__name__
    return text.splitlines()[0][:200]


_COMPRESS_EXT = {
    "gzip": ".tar.gz",
    "bzip2": ".tar.bz2",
    "xz": ".tar.xz",
    "zstd": ".tar.zst",
    "none": ".tar",
}
