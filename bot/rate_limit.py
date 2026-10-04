"""Rate limiter with sliding window and request queue for subdomain API."""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from bot.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class QueuedRequest:
    """A request waiting in the queue."""
    future: asyncio.Future
    domain: str
    search_func: Callable[[], Any]
    queued_at: float = field(default_factory=time.time)
    status_message_update: Optional[Callable[[str], Any]] = None


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for 60 requests per 60 seconds."""
    
    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_times: Deque[float] = deque()
        self._lock = asyncio.Lock()
        # Track API rate limit headers if provided
        self._api_limit_remaining: Optional[int] = None
        self._api_limit_reset: Optional[float] = None
    
    async def update_from_headers(self, headers: Dict[str, str]) -> None:
        """Update rate limit info from API response headers."""
        async with self._lock:
            if "x-ratelimit-remaining" in headers:
                try:
                    self._api_limit_remaining = int(headers["x-ratelimit-remaining"])
                except ValueError:
                    pass
            if "x-ratelimit-reset" in headers:
                try:
                    self._api_limit_reset = float(headers["x-ratelimit-reset"])
                except ValueError:
                    pass
    
    async def get_remaining(self) -> int:
        """Get estimated remaining requests in current window."""
        async with self._lock:
            now = time.time()
            # Remove old entries
            cutoff = now - self.window_seconds
            while self.request_times and self.request_times[0] < cutoff:
                self.request_times.popleft()
            
            local_remaining = max(0, self.max_requests - len(self.request_times))
            
            # Use API header if available and more restrictive
            if self._api_limit_remaining is not None:
                return min(local_remaining, self._api_limit_remaining)
            return local_remaining
    
    async def get_wait_time(self) -> float:
        """Get time until next request slot is available."""
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            while self.request_times and self.request_times[0] < cutoff:
                self.request_times.popleft()
            
            if len(self.request_times) < self.max_requests:
                return 0.0
            
            # Time until oldest request expires
            wait = self.request_times[0] + self.window_seconds - now
            return max(0.0, wait)
    
    async def acquire(self) -> None:
        """Acquire a rate limit slot, waiting if necessary."""
        while True:
            wait = await self.get_wait_time()
            if wait <= 0:
                async with self._lock:
                    self.request_times.append(time.time())
                return
            logger.debug(f"Rate limit reached, waiting {wait:.1f}s")
            await asyncio.sleep(min(wait, 1.0))  # Check every second
    
    async def record_request(self) -> None:
        """Record a request (for manual tracking)."""
        async with self._lock:
            self.request_times.append(time.time())
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status."""
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            while self.request_times and self.request_times[0] < cutoff:
                self.request_times.popleft()
            
            return {
                "requests_in_window": len(self.request_times),
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "remaining": max(0, self.max_requests - len(self.request_times)),
                "api_remaining": self._api_limit_remaining,
                "api_reset": self._api_limit_reset,
            }


class RateLimitedQueue:
    """Queue for processing subdomain searches with rate limiting."""
    
    def __init__(
        self,
        rate_limiter: SlidingWindowRateLimiter,
        max_concurrent: int = 3,
        status_update_interval: float = 20.0,
        min_status_edit_interval: float = 15.0,
    ):
        self.rate_limiter = rate_limiter
        self.max_concurrent = max_concurrent
        self.status_update_interval = status_update_interval
        self.min_status_edit_interval = min_status_edit_interval
        
        self._queue: Deque[QueuedRequest] = deque()
        self._processing: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._last_status_edit: Dict[str, float] = {}
    
    async def start(self) -> None:
        """Start the queue worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Rate-limited queue started")
    
    async def stop(self) -> None:
        """Stop the queue worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        # Wait for in-flight requests
        if self._processing:
            await asyncio.gather(*self._processing.values(), return_exceptions=True)
        logger.info("Rate-limited queue stopped")
    
    def enqueue(
        self,
        domain: str,
        search_func: Callable[[], Any],
        status_update: Optional[Callable[[str], Any]] = None,
    ) -> asyncio.Future:
        """Add a search request to the queue. Returns a future that resolves with the result."""
        future = asyncio.get_event_loop().create_future()
        request = QueuedRequest(
            future=future,
            domain=domain,
            search_func=search_func,
            status_message_update=status_update,
        )
        self._queue.append(request)
        logger.info(f"Queued search for {domain} (queue size: {len(self._queue)})")
        return future
    
    async def _worker(self) -> None:
        """Background worker that processes the queue."""
        while self._running:
            try:
                await self._process_queue()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Queue worker error: {e}")
                await asyncio.sleep(1)
    
    async def _process_queue(self) -> None:
        """Process queued requests respecting rate limit."""
        # Clean up completed tasks
        done = [domain for domain, task in self._processing.items() if task.done()]
        for domain in done:
            del self._processing[domain]
        
        # Check if we can process more
        if len(self._processing) >= self.max_concurrent:
            await asyncio.sleep(0.5)
            return
        
        if not self._queue:
            await asyncio.sleep(0.5)
            return
        
        # Get next request
        request = self._queue.popleft()
        
        # Wait for rate limiter
        await self.rate_limiter.acquire()
        
        # Start processing
        task = asyncio.create_task(self._process_request(request))
        self._processing[request.domain] = task
    
    async def _process_request(self, request: QueuedRequest) -> None:
        """Process a single queued request with status updates."""
        domain = request.domain
        start_time = time.time()
        
        try:
            # Initial status
            if request.status_message_update:
                await self._safe_status_update(
                    request.status_message_update,
                    f"🔍 Searching for {domain}... (started)"
                )
            
            # Run the search with periodic status updates
            result = await self._run_with_status_updates(request)
            
            # Success
            request.future.set_result(result)
            logger.info(f"Completed search for {domain} in {time.time() - start_time:.1f}s")
            
        except Exception as e:
            logger.error(f"Search failed for {domain}: {e}")
            request.future.set_exception(e)
        finally:
            # Clean up
            if domain in self._processing:
                del self._processing[domain]
    
    async def _run_with_status_updates(self, request: QueuedRequest) -> Any:
        """Run search function with periodic status updates."""
        domain = request.domain
        status_fn = request.status_message_update
        last_update = 0
        
        if not status_fn:
            # No status updates needed
            return await request.search_func()
        
        # Create a task for the search
        search_task = asyncio.create_task(request.search_func())
        
        # Monitor and update status
        while not search_task.done():
            await asyncio.sleep(5)  # Check every 5 seconds
            
            elapsed = time.time() - request.queued_at
            now = time.time()
            
            # Check if enough time passed for status edit
            if now - self._last_status_edit.get(domain, 0) >= self.min_status_edit_interval:
                queue_pos = self._get_queue_position(domain)
                if queue_pos > 0:
                    msg = f"🔍 Searching for {domain}... (position in queue: {queue_pos})"
                else:
                    msg = f"🔍 Searching for {domain}... ({elapsed:.0f}s elapsed)"
                
                await self._safe_status_update(status_fn, msg)
                self._last_status_edit[domain] = now
            
            # Small sleep to not busy-wait
            await asyncio.sleep(0.1)
        
        # Get result
        try:
            result = await search_task
        except Exception as e:
            search_task.cancel()
            raise e
        
        # Final status
        await self._safe_status_update(status_fn, f"✅ Found results for {domain}")
        
        return result
    
    def _get_queue_position(self, domain: str) -> int:
        """Get position of domain in queue (1-based)."""
        for i, req in enumerate(self._queue):
            if req.domain == domain:
                return i + 1
        return 0
    
    async def _safe_status_update(self, update_fn: Callable[[str], Any], text: str) -> None:
        """Safely call status update function."""
        try:
            await update_fn(text)
        except Exception as e:
            logger.warning(f"Failed to update status message: {e}")
    
    async def get_queue_info(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            "queue_length": len(self._queue),
            "processing": len(self._processing),
            "max_concurrent": self.max_concurrent,
            "queued_domains": [r.domain for r in self._queue],
            "processing_domains": list(self._processing.keys()),
        }


# Global instances
_rate_limiter: Optional[SlidingWindowRateLimiter] = None
_rate_queue: Optional[RateLimitedQueue] = None


async def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_settings()
        _rate_limiter = SlidingWindowRateLimiter(
            max_requests=60,  # API limit: 60/min
            window_seconds=60.0,
        )
    return _rate_limiter


async def get_rate_queue() -> RateLimitedQueue:
    """Get or create the global rate-limited queue."""
    global _rate_queue
    if _rate_queue is None:
        limiter = await get_rate_limiter()
        settings = get_settings()
        _rate_queue = RateLimitedQueue(
            rate_limiter=limiter,
            max_concurrent=3,
            status_update_interval=20.0,
            min_status_edit_interval=15.0,
        )
    return _rate_queue


async def init_rate_limiting() -> None:
    """Initialize rate limiting system."""
    queue = await get_rate_queue()
    await queue.start()
    logger.info("Rate limiting initialized")


async def shutdown_rate_limiting() -> None:
    """Shutdown rate limiting system."""
    global _rate_queue
    if _rate_queue:
        await _rate_queue.stop()
        _rate_queue = None