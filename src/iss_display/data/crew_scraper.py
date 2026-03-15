"""Custom web scraper for current ISS crew data.

Drop-in replacement for AstrosClient when CREW_SOURCE=scraper.
Implement _scrape() to parse the target page and return a list of CrewMember.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import requests

from iss_display.data.astros_client import AstrosData, CrewMember

logger = logging.getLogger(__name__)

_SCRAPE_URL = ""  # TODO: set the target URL here
_TIMEOUT = (3.05, 10)
_REFRESH_INTERVAL = 3600.0  # 1 hour


class CrewScraper:
    """Scrapes current ISS crew from a web page.

    Caches results and refreshes every hour. Never raises —
    returns stale cache on failure, or None if no data has ever
    been fetched successfully.

    To implement: fill in _SCRAPE_URL and complete _scrape().
    """

    def __init__(self):
        self._session = requests.Session()
        self._cached: Optional[AstrosData] = None
        self._last_fetch: float = 0.0
        self._consecutive_failures: int = 0

    def get_astros(self, force: bool = False) -> Optional[AstrosData]:
        """Return crew data, refreshing if stale (>1 hour) or forced."""
        now = time.monotonic()
        if not force and self._cached is not None and (now - self._last_fetch) < _REFRESH_INTERVAL:
            return self._cached

        try:
            if not _SCRAPE_URL:
                raise NotImplementedError("_SCRAPE_URL is not set in crew_scraper.py")

            resp = self._session.get(_SCRAPE_URL, timeout=_TIMEOUT)
            resp.raise_for_status()
            crew = self._scrape(resp.text)

            self._cached = AstrosData(
                count=len(crew),
                crew=crew,
                timestamp=time.time(),
            )
            self._last_fetch = now
            self._consecutive_failures = 0
            logger.debug("Scraped crew: %d people", self._cached.count)
        except NotImplementedError as e:
            logger.error("CrewScraper not implemented: %s", e)
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning("CrewScraper failed (%dx): %s", self._consecutive_failures, e)

        return self._cached

    def _scrape(self, html: str) -> List[CrewMember]:
        """Parse the page HTML and return a list of CrewMember.

        TODO: implement this method.

        Args:
            html: raw HTML of the page at _SCRAPE_URL

        Returns:
            list of CrewMember(name=..., craft=...)

        Example:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            # ... parse and return crew list
        """
        raise NotImplementedError("_scrape() is not yet implemented")

    def reset_session(self):
        """Close and recreate the HTTP session."""
        try:
            self._session.close()
        except Exception:
            pass
        self._session = requests.Session()


__all__ = ["CrewScraper"]
