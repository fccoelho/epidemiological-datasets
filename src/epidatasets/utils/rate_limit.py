"""Rate limiter for API requests."""

from __future__ import annotations

import time
from typing import Optional


class RateLimiter:
    """Simple rate limiter for API requests.

    Parameters
    ----------
    requests_per_second : float
        Maximum number of requests allowed per second.
    """

    def __init__(self, requests_per_second: float = 1.0) -> None:
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time: Optional[float] = None

    def wait_if_needed(self) -> None:
        """Wait if necessary to maintain rate limit."""
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)

        self.last_request_time = time.time()
