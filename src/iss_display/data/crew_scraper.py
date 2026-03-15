"""Crew data client for isslivenow.com.

Calls the isslivenow.com backend API directly, spoofing the Origin header
to pass its CORS check. Refreshes once per hour.

Drop-in replacement for AstrosClient when CREW_SOURCE=scraper.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import List, Optional

import requests

from iss_display.data.astros_client import AstrosData, CrewMember

logger = logging.getLogger(__name__)

_API_URL = "https://us-central1-iss-hd-live-android.cloudfunctions.net/getAstronautsData"
_HEADERS = {
    "Origin": "https://isslivenow.com",
    "Referer": "https://isslivenow.com/",
}
_TIMEOUT = (3.05, 10)
_REFRESH_INTERVAL = 3600.0  # 1 hour


class CrewScraper:
    """Fetches current ISS crew from the isslivenow.com backend API.

    Caches results and refreshes every hour. Never raises —
    returns stale cache on failure, or None if no data has ever
    been fetched successfully.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._cached: Optional[AstrosData] = None
        self._last_fetch: float = 0.0
        self._consecutive_failures: int = 0

    def get_astros(self, force: bool = False) -> Optional[AstrosData]:
        """Return crew data, refreshing if stale (>1 hour) or forced."""
        now = time.monotonic()
        if not force and self._cached is not None and (now - self._last_fetch) < _REFRESH_INTERVAL:
            return self._cached

        try:
            resp = self._session.get(_API_URL, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success", False):
                raise ValueError(f"API returned failure: {data}")

            crew = self._parse(data)
            self._cached = AstrosData(
                count=len(crew),
                crew=crew,
                timestamp=time.time(),
            )
            self._last_fetch = now
            self._consecutive_failures = 0
            logger.debug("Fetched crew from isslivenow: %d people", self._cached.count)
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning("CrewScraper failed (%dx): %s", self._consecutive_failures, e)

        return self._cached

    def _parse(self, data: dict) -> List[CrewMember]:
        """Parse the API JSON response into a list of CrewMember.

        Response shape:
            {"success": true, "count": 7, "data": {"Key_Name": {"name": "...", "launchDate": "YYYY-MM-DD", ...}, ...}}
        All crew are on the ISS so craft is hardcoded.
        """
        crew = []
        today = date.today()
        for person in data.get("data", {}).values():
            name = person.get("name", "")
            if not name:
                continue
            days = None
            launch_str = person.get("launchDate", "")
            if launch_str:
                try:
                    days = (today - date.fromisoformat(launch_str)).days
                except ValueError:
                    pass
            crew.append(CrewMember(name=name, craft="ISS", days_in_space=days))
        return crew

    def reset_session(self):
        """Close and recreate the HTTP session."""
        try:
            self._session.close()
        except Exception:
            pass
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)


__all__ = ["CrewScraper"]
