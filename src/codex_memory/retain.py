from __future__ import annotations

import re


class UnsafeContentError(ValueError):
    """Raised when retained content is unsafe to store or inject later."""


_SECRET_PATTERNS = [
    re.compile(r"\b[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)[A-Z0-9_]*\s*=", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b\.env\b"),
]

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions", re.I),
    re.compile(r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", re.I),
    re.compile(r"reveal\s+the\s+system\s+prompt", re.I),
    re.compile(r"system\s+prompt\s+override", re.I),
]

_INVISIBLE_CHARS = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}


def validate_retain_content(content: str, *, max_chars: int = 800) -> None:
    text = (content or "").strip()
    if not text:
        raise UnsafeContentError("content cannot be empty")
    if len(text) > max_chars:
        raise UnsafeContentError(f"content exceeds {max_chars} characters")
    for char in _INVISIBLE_CHARS:
        if char in text:
            raise UnsafeContentError("content contains invisible unicode")
    for pattern in [*_SECRET_PATTERNS, *_INJECTION_PATTERNS]:
        if pattern.search(text):
            raise UnsafeContentError("content matches unsafe pattern")
