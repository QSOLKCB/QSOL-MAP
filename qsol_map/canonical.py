"""Canonical serialization and domain-separated hashing for QSOL-MAP."""

from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_SAFE_INTEGER = (1 << 53) - 1


class CanonicalizationError(ValueError):
    """Raised when a value cannot enter an identity-bearing JSON document."""


def _validate(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise CanonicalizationError(
                f"{path}: integer outside portable safe range; encode large integers as strings"
            )
        return
    if isinstance(value, float):
        raise CanonicalizationError(f"{path}: floating-point values are forbidden")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"{path}: object keys must be strings")
            _validate(item, f"{path}.{key}")
        return
    raise CanonicalizationError(f"{path}: unsupported type {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes with no trailing newline.

    Identity-bearing numbers are restricted to the interoperable integer range.
    Large exact values must be represented explicitly as decimal strings.
    """
    _validate(value)
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def domain_sha256(domain: str, payload: bytes) -> str:
    if not domain or "\x00" in domain:
        raise ValueError("domain must be a non-empty NUL-free string")
    h = hashlib.sha256()
    h.update(domain.encode("utf-8"))
    h.update(b"\x00")
    h.update(payload)
    return h.hexdigest()
