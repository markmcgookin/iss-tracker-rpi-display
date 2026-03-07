"""Client for the People in Space API (open-notify.org)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

_ASTROS_URL = "http://api.open-notify.org/astros.json"
_TIMEOUT = (3.05, 8)
_REFRESH_INTERVAL = 300.0  # 5 minutes


@dataclass(frozen=True)
class CrewMember:
    name: str
    craft: str


@dataclass(frozen=True)
class AstrosData:
    count: int
    crew: List[CrewMember]
    timestamp: float


class AstrosClient:
    """Fetches current astronauts in space from open-notify.org.

    Caches results and refreshes every 5 minutes.  Never raises —
    returns stale cache on failure, or None if no data has ever
    been fetched successfully.
    """

    def __init__(self):
        self._session = requests.Session()
        self._cached: Optional[AstrosData] = None
        self._last_fetch: float = 0.0
        self._consecutive_failures: int = 0

    def get_astros(self, force: bool = False) -> Optional[AstrosData]:
        """Return crew data, refreshing if stale (>5 min) or forced."""
        now = time.monotonic()
        if not force and self._cached is not None and (now - self._last_fetch) < _REFRESH_INTERVAL:
            return self._cached

        try:
            resp = self._session.get(_ASTROS_URL, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            crew = [
                CrewMember(name=p["name"], craft=p["craft"])
                for p in data.get("people", [])
            ]
            self._cached = AstrosData(
                count=data.get("number", len(crew)),
                crew=crew,
                timestamp=time.time(),
            )
            self._last_fetch = now
            self._consecutive_failures = 0
            logger.debug("Fetched astros: %d people", self._cached.count)
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning("Astros API failed (%dx): %s", self._consecutive_failures, e)

        return self._cached

    def reset_session(self):
        """Close and recreate the HTTP session."""
        try:
            self._session.close()
        except Exception:
            pass
        self._session = requests.Session()


__all__ = ["AstrosClient", "AstrosData", "CrewMember"]
