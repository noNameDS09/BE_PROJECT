"""Polite, caching HTTP client for SEC EDGAR.

SEC requires a User-Agent naming a contact and allows at most 10 requests per
second. Every response is stored under `raw_dir` mirroring the URL path, so a
fetch is done once and every later run reads from disk.
"""

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5


class SecClient:
    def __init__(
        self,
        user_agent: str,
        raw_dir: Path,
        rps: float = 8.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not user_agent or "@" not in user_agent:
            raise ValueError("SEC_USER_AGENT must include a contact email (see .env.example)")
        self.raw_dir = raw_dir
        self._interval = 1.0 / rps
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None
        self._http = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            transport=transport,
            timeout=60.0,
            follow_redirects=True,
        )

    def cache_path(self, url: str) -> Path:
        parts = urlsplit(url)
        path = parts.path.lstrip("/") or "index"
        if parts.query:
            path += "__" + hashlib.sha256(parts.query.encode()).hexdigest()[:16]
        return self.raw_dir / parts.netloc / path

    def get(self, url: str, *, refresh: bool = False) -> bytes:
        target = self.cache_path(url)
        if target.exists() and not refresh:
            return target.read_bytes()
        body = self._fetch(url)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return body

    def get_json(self, url: str, *, refresh: bool = False) -> Any:
        return json.loads(self.get(url, refresh=refresh))

    def _fetch(self, url: str) -> bytes:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._throttle()
            resp = self._http.get(url)
            if resp.status_code == 200:
                return resp.content
            if resp.status_code not in RETRY_STATUS or attempt == MAX_ATTEMPTS:
                resp.raise_for_status()
            self._sleep(2.0 * 2 ** (attempt - 1))
        raise AssertionError("unreachable")

    def _throttle(self) -> None:
        now = self._clock()
        if self._last is not None and (wait := self._interval - (now - self._last)) > 0:
            self._sleep(wait)
        self._last = self._clock()
