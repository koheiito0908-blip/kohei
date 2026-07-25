"""Polite HTTP fetching for boatrace.jp.

BOAT RACE公式サイトへの負荷を抑えるため、リクエスト間隔を空け、
失敗時は指数バックオフでリトライする。
"""
from __future__ import annotations

import io
import time
from typing import IO

import requests

USER_AGENT = "kyotei-heiwajima-predictor/1.0 (+https://github.com/; personal non-commercial use)"

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def fetch_text(url: str, *, delay: float = 0.4, retries: int = 3, timeout: float = 15.0) -> str:
    """Fetch a URL's body as text (one network call). Always sleeps `delay`
    seconds before returning/raising, to keep request pacing polite regardless
    of outcome."""
    last_error: Exception | None = None
    try:
        for attempt in range(retries):
            try:
                resp = _session.get(url, timeout=timeout)
                resp.raise_for_status()
                resp.encoding = resp.encoding or "utf-8"
                return resp.text
            except requests.RequestException as exc:  # network hiccup / 5xx
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"failed to fetch {url}") from last_error
    finally:
        time.sleep(delay)


def fetch(url: str, *, delay: float = 0.4, retries: int = 3, timeout: float = 15.0) -> IO[str]:
    """Fetch a URL and return its body as a fresh text stream (one network call)."""
    return io.StringIO(fetch_text(url, delay=delay, retries=retries, timeout=timeout))
