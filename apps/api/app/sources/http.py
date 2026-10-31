"""HTTP for job sources: a polite client that identifies itself, waits
between calls, and keeps answers for a while so many searches asking the
same thing make one call.

Each source class has one `Fetcher`, shared by every search in the process
(the worker), so its cache and its pace hold across runs.
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from typing import Any

import httpx2

USER_AGENT = "JobHunter/0.1 (+https://github.com/RichardHuang24/job-hunter)"


class SourceError(RuntimeError):
    """A source answered with an error, or not at all. The message is
    shown with the search run, so it says what happened in plain words."""


class Fetcher:
    def __init__(self, *, min_interval: float = 1.0, ttl: float = 0.0, max_entries: int = 500,
                 timeout: float = 20.0, client: httpx2.Client | None = None):
        self.min_interval, self.ttl, self.max_entries = min_interval, ttl, max_entries
        self.client = client or httpx2.Client(timeout=timeout, follow_redirects=True)
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._last_call = 0.0
        self.calls = 0  # network calls made, for tests and logs

    def _wait_turn(self) -> None:
        wait = self._last_call + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def get(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> httpx2.Response:
        """One call, at the source's pace. Raises SourceError when it can't connect."""
        with self._lock:
            self._wait_turn()
            self.calls += 1
            try:
                return self.client.get(url, params=params, headers={"User-Agent": USER_AGENT, **(headers or {})})
            except httpx2.TimeoutException as exc:
                raise SourceError(f"{_host(url)} didn't answer in time") from exc
            except httpx2.TransportError as exc:
                raise SourceError(f"Couldn't reach {_host(url)}") from exc

    def json(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        """A JSON answer, from the cache when it's fresh enough."""
        cache_key = url + "?" + json.dumps(params or {}, sort_keys=True, default=str)
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(cache_key)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        response = self.get(url, params, headers)
        if response.status_code == 429:
            after = response.headers.get("retry-after", "")
            raise SourceError(f"{_host(url)} is rate-limiting us" + (f" - try again in {after} s" if after.isdigit() else ""))
        if response.status_code >= 400:
            raise SourceError(f"{_host(url)} answered {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError(f"{_host(url)} sent something that isn't JSON") from exc
        if self.ttl > 0:
            with self._lock:
                self._cache[cache_key] = (time.monotonic(), data)
                self._cache.move_to_end(cache_key)
                while len(self._cache) > self.max_entries:
                    self._cache.popitem(last=False)
        return data

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


def _host(url: str) -> str:
    return httpx2.URL(url).host or url
