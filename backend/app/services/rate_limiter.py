"""Rate limiting service for API endpoints.

Provides sliding-window rate limiting for protected API endpoints such as AI intake.
"""

import collections
import logging
import math
import threading
import time
from typing import Dict, List, Tuple

logger = logging.getLogger("orqestra.rate_limiter")


class BaseRateLimiter:
    """Abstract interface for request rate limiting."""

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int]:
        """Check whether request is allowed under the rate limit.

        Args:
            key: Unique identifier for rate-limiting bucket (e.g. business_id:user_id).
            max_requests: Maximum allowed requests within the time window.
            window_seconds: Window duration in seconds.

        Returns:
            Tuple of (is_allowed: bool, retry_after_seconds: int).
        """
        raise NotImplementedError


class InMemoryRateLimiter(BaseRateLimiter):
    """Thread-safe sliding-window in-memory rate limiter.

    Architectural & Deployment Scope:
    --------------------------------
    This implementation tracks sliding-window request timestamps in memory
    per process instance. It is thread-safe via threading.Lock and suitable
    for single-worker deployments, local development, and test environments.

    Production / Multi-Worker Deployment Limitation:
    In a distributed or multi-process deployment (such as multiple Gunicorn or
    Uvicorn workers across separate containers or instances), enforcement is
    process-local: each worker maintains its own memory bucket. For unified global
    enforcement across distributed worker pools, a backing distributed store
    (such as Redis with sliding log or token-bucket Lua scripts) would be required.

    Fail-Safe Behavior:
    If any unexpected exception occurs during rate check, the limiter logs a warning
    without exposing sensitive request details, prompts, or credentials, and fails
    open (allows the request) so service availability is preserved.
    """

    def __init__(self, purge_interval_seconds: int = 300):
        self._lock = threading.Lock()
        self._history: Dict[str, List[float]] = collections.defaultdict(list)
        self._last_purge: float = time.monotonic()
        self._purge_interval: int = purge_interval_seconds

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int]:
        """Check whether a request for the given key is allowed under sliding window."""
        try:
            now = time.monotonic()
            cutoff = now - float(window_seconds)

            with self._lock:
                # Periodic maintenance to prevent unbounded memory growth
                if now - self._last_purge > self._purge_interval:
                    self._purge_expired(now)

                timestamps = self._history[key]
                # Filter out timestamps older than the sliding window cutoff
                valid_timestamps = [ts for ts in timestamps if ts > cutoff]
                self._history[key] = valid_timestamps

                if len(valid_timestamps) >= max_requests:
                    # Oldest timestamp in window determines when slot frees up
                    oldest = valid_timestamps[0]
                    remaining = oldest + float(window_seconds) - now
                    retry_after = max(1, math.ceil(remaining))
                    logger.warning(
                        f"Rate limit exceeded for bucket key={key[:16]}... "
                        f"({len(valid_timestamps)}/{max_requests} reqs in {window_seconds}s)"
                    )
                    return False, retry_after

                # Record current request timestamp
                valid_timestamps.append(now)
                return True, 0

        except Exception as e:
            logger.error(f"Rate limiter failure; failing open: {e}")
            return True, 0

    def _purge_expired(self, now: float) -> None:
        """Purge keys that have had no activity for over an hour."""
        stale_cutoff = now - 3600.0
        keys_to_delete = [
            k for k, timestamps in self._history.items()
            if not timestamps or timestamps[-1] < stale_cutoff
        ]
        for k in keys_to_delete:
            del self._history[k]
        self._last_purge = now

    def reset(self) -> None:
        """Reset all rate limiter history (primarily for tests)."""
        with self._lock:
            self._history.clear()
            self._last_purge = time.monotonic()

