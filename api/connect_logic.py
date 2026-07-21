"""Validation, rate limiting, and content checks for connect submissions."""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

_URL_PATTERN = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)
_SPAM_PATTERNS = [
    re.compile(r"\bviagra\b", re.I),
    re.compile(r"\bcialis\b", re.I),
    re.compile(r"click\s+here\s+now", re.I),
    re.compile(r"buy\s+cheap\s+\w+", re.I),
    re.compile(r"congratulations[, ]+you\s+(have\s+)?won", re.I),
    re.compile(r"crypto\s+investment", re.I),
]

_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: Dict[str, Deque[float]] = defaultdict(deque)
_RATE_WINDOW_SEC = 3600
_RATE_MAX_PER_WINDOW = 5


def strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def normalize_user_text(text: str, max_len: int) -> str:
    s = strip_html_tags(text or "")
    s = s.strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s


def count_urls(text: str) -> int:
    return len(_URL_PATTERN.findall(text or ""))


def matches_spam_heuristics(text: str) -> bool:
    t = text or ""
    return any(p.search(t) for p in _SPAM_PATTERNS)


def rate_limit_allow(ip: str) -> bool:
    """Return True if this IP may submit (under 5 per rolling hour)."""
    now = time.time()
    cutoff = now - _RATE_WINDOW_SEC
    with _RATE_LOCK:
        dq = _RATE_BUCKETS[ip]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= _RATE_MAX_PER_WINDOW:
            return False
        dq.append(now)
        return True


def rate_limit_undo(ip: str) -> None:
    """If validation failed after increment, remove last hit for this IP."""
    with _RATE_LOCK:
        dq = _RATE_BUCKETS.get(ip)
        if dq:
            dq.pop()


def reset_rate_limits_for_tests() -> None:
    with _RATE_LOCK:
        _RATE_BUCKETS.clear()
