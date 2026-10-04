import time
import asyncio
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from .config import settings
from .logging import logger

# Global asynchronous concurrency semaphore to protect CPU from ML task saturation
analysis_semaphore = asyncio.Semaphore(settings.max_concurrent_analysis)

class InMemoryRateLimiter:
    """
    Sliding window rate limiter per client IP.
    Avoids external dependencies while preventing abuse on public prototypes.
    """
    def __init__(self):
        # Format: {ip: [timestamp1, timestamp2, ...]}
        self._requests: Dict[str, list] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _extract_client_ip(request: Request) -> str:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def check_rate_limit(self, request: Request, max_requests: int = 10, window_seconds: int = 60):
        client_ip = self._extract_client_ip(request)
        now = time.time()
        
        async with self._lock:
            # Clean expired timestamps
            if client_ip in self._requests:
                self._requests[client_ip] = [
                    t for t in self._requests[client_ip] if now - t < window_seconds
                ]
            else:
                self._requests[client_ip] = []

            # Check if limit exceeded
            if len(self._requests[client_ip]) >= max_requests:
                logger.warning(f"Rate limit exceeded for IP: {client_ip} ({len(self._requests[client_ip])} reqs in {window_seconds}s)")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds permitted for document processing."
                )

            # Record current request
            self._requests[client_ip].append(now)

rate_limiter = InMemoryRateLimiter()

async def rate_limit_analysis(request: Request):
    """Rate limit dependency for heavy ML/CV analysis routes."""
    await rate_limiter.check_rate_limit(
        request,
        max_requests=settings.rate_limit_analyze_per_minute,
        window_seconds=60
    )
