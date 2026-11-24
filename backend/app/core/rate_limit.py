"""In-memory sliding window rate limiter supporting Retry-After headers."""
import time
from collections import defaultdict
from fastapi import HTTPException, Request, status
from app.core.config import settings


class RateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, rate_str: str) -> None:
        parts = rate_str.split("/")
        self.limit = int(parts[0])
        unit = parts[1].lower() if len(parts) > 1 else "minute"
        self.window_seconds = 60 if "minute" in unit else (3600 if "hour" in unit else 1)
        self.requests: dict[str, list[float]] = defaultdict(list)

    def check(self, request: Request) -> None:
        # Resolve client IP address
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        window_start = now - self.window_seconds

        # Prune expired timestamps
        timestamps = [t for t in self.requests[client_ip] if t > window_start]
        self.requests[client_ip] = timestamps

        if len(timestamps) >= self.limit:
            # Calculate remaining seconds before the oldest request clears the window
            retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again shortly.",
                headers={"Retry-After": str(max(1, retry_after))},
            )
        self.requests[client_ip].append(now)

chat_limiter = RateLimiter(settings.CHAT_RATE_LIMIT)
session_limiter = RateLimiter(settings.SESSION_RATE_LIMIT)
