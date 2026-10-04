"""Async API client for subdomain lookup with retries, caching, and error handling."""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from bot.cache import get_from_cache, set_cache
from bot.config import get_settings
from bot.rate_limit import get_rate_limiter, get_rate_queue

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, error_type: str = "unknown"):
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type


class InvalidDomainError(APIError):
    """Raised when the domain is invalid."""

    def __init__(self, message: str = "Invalid domain"):
        super().__init__(message, status_code=400, error_type="invalid_domain")


class RateLimitError(APIError):
    """Raised when rate limited by the API."""

    def __init__(self, message: str = "Rate limited", retry_after: Optional[int] = None):
        super().__init__(message, status_code=429, error_type="api_rate_limit")
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """Raised when API authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401, error_type="unauthorized")


class ForbiddenError(APIError):
    """Raised when API access is forbidden."""

    def __init__(self, message: str = "Access forbidden"):
        super().__init__(message, status_code=403, error_type="forbidden")


class TimeoutError(APIError):
    """Raised when request times out."""

    def __init__(self, message: str = "Request timeout"):
        super().__init__(message, status_code=None, error_type="timeout")


class SubdomainAPIClient:
    """Async client for the subdomain lookup API with rate limiting and disk cache."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 180,
        cache_ttl: int = 600,
        proxy_url: Optional[str] = None,
        bypass_rate_limit: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.proxy_url = proxy_url
        self.bypass_rate_limit = bypass_rate_limit

        # HTTP client with connection pooling
        self._client: Optional[httpx.AsyncClient] = None
        
        # Rate limiting will be handled by the global rate limiter
        self._rate_limiter = None
        self._rate_queue = None

    async def _init_rate_limiting(self) -> None:
        """Initialize rate limiting components."""
        if self._rate_limiter is None:
            self._rate_limiter = await get_rate_limiter()
            self._rate_queue = await get_rate_queue()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Accept": "text/plain"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Configure proxy if provided
            proxy = self.proxy_url
            if proxy:
                logger.debug(f"Using proxy for API client: {proxy}")

            # Force IPv4 and configure timeouts
            transport = httpx.AsyncHTTPTransport(
                local_address="0.0.0.0",  # Force IPv4
                retries=0,  # We handle retries ourselves
            )

            self._client = httpx.AsyncClient(
                transport=transport,
                timeout=httpx.Timeout(self.timeout, connect=30.0, read=self.timeout, write=self.timeout),
                headers=headers,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                proxy=proxy,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _parse_response(self, response: httpx.Response) -> Tuple[List[str], Dict[str, str]]:
        """
        Parse API response into list of subdomains.
        Returns (subdomains, rate_limit_headers)
        """
        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            # Try to parse JSON error or unexpected JSON response
            try:
                data = response.json()
                if isinstance(data, dict) and "error" in data:
                    raise APIError(
                        data.get("message", "API error"),
                        status_code=response.status_code,
                        error_type=data.get("error", "unknown").lower(),
                    )
                # If it's a JSON array, treat as subdomain list
                if isinstance(data, list):
                    return [str(item).strip() for item in data if str(item).strip()], dict(response.headers)
            except httpx.ResponseNotRead:
                pass
            except Exception:
                pass

        # Default: plain text, one subdomain per line
        text = response.text.strip()
        if not text:
            return [], dict(response.headers)

        subdomains = [line.strip() for line in text.split("\n") if line.strip()]
        return subdomains, dict(response.headers)

    async def search(
        self,
        domain: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        status_update: Optional[Callable[[str], Any]] = None,
    ) -> List[str]:
        """
        Search for subdomains of a domain.

        This method now uses the global rate-limited queue to ensure
        we never exceed the API's 60 requests/minute limit.

        Args:
            domain: Target domain (e.g., example.com)
            max_retries: Maximum number of retry attempts (for transient errors)
            base_delay: Base delay for exponential backoff (seconds)

        Returns:
            List of discovered subdomains

        Raises:
            InvalidDomainError: If domain is invalid
            RateLimitError: If rate limited
            AuthenticationError: If API key is invalid
            ForbiddenError: If access forbidden
            TimeoutError: If request times out
            APIError: For other API errors
        """
        # Initialize rate limiting (unless bypassed)
        if not self.bypass_rate_limit:
            await self._init_rate_limiting()
        
        # Check cache first (L1 memory + L2 disk)
        cached = await get_from_cache(domain, self.cache_ttl)
        if cached is not None:
            logger.info(f"Cache hit for domain: {domain} ({len(cached)} subdomains)")
            return cached

        if self.bypass_rate_limit:
            # Direct call without rate limiting (for testing)
            return await self._do_search_direct(domain, max_retries, base_delay)
        
        # Define the actual search function that will be queued
        async def do_search() -> List[str]:
            return await self._do_search_direct(domain, max_retries, base_delay)

        # Enqueue the search in the rate-limited queue
        # This ensures we never exceed 60 requests/minute
        return await self._rate_queue.enqueue(domain, do_search, status_update)

    async def _do_search_direct(
        self,
        domain: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> List[str]:
        """Direct search without rate limiting (for testing or cache hits)."""
        client = await self._get_client()
        params = {"domain": domain}

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                logger.info(f"API request for domain: {domain} (attempt {attempt + 1}/{max_retries + 1})")
                response = await client.get(f"{self.base_url}/v1/search", params=params)

                # Update rate limiter with headers (if available)
                if self._rate_limiter:
                    await self._rate_limiter.update_from_headers(dict(response.headers))

                # Handle different status codes
                if response.status_code == 200:
                    subdomains, headers = self._parse_response(response)
                    
                    # Update rate limiter with response headers
                    if self._rate_limiter:
                        await self._rate_limiter.update_from_headers(headers)
                    
                    # Cache the result
                    await set_cache(domain, subdomains)
                    logger.info(f"Found {len(subdomains)} subdomains for {domain}")
                    return subdomains

                elif response.status_code == 400:
                    # Invalid domain
                    try:
                        error_data = response.json()
                        raise InvalidDomainError(error_data.get("message", "Invalid domain"))
                    except Exception:
                        raise InvalidDomainError("Invalid domain format")

                elif response.status_code == 401:
                    raise AuthenticationError("Invalid API key")

                elif response.status_code == 403:
                    raise ForbiddenError("Access forbidden")

                elif response.status_code == 429:
                    # Rate limited - check for retry-after header
                    retry_after = None
                    if "retry-after" in response.headers:
                        try:
                            retry_after = int(response.headers["retry-after"])
                        except ValueError:
                            pass
                    # Update rate limiter with headers
                    if self._rate_limiter:
                        await self._rate_limiter.update_from_headers(dict(response.headers))
                    raise RateLimitError(
                        response.text or "Rate limit exceeded",
                        retry_after=retry_after,
                    )

                elif response.status_code >= 500:
                    # Server error - retry
                    raise APIError(f"Server error: {response.status_code}", status_code=response.status_code)

                else:
                    # Other client errors
                    raise APIError(
                        f"API error: {response.status_code} - {response.text[:200]}",
                        status_code=response.status_code,
                    )

            except httpx.TimeoutException as e:
                last_exception = TimeoutError(f"Request timeout after {self.timeout}s")
                logger.warning(f"Timeout for {domain}: {e}")

            except httpx.NetworkError as e:
                last_exception = APIError(f"Network error: {e}")
                logger.warning(f"Network error for {domain}: {e}")

            except APIError:
                # Re-raise API errors immediately (don't retry client errors)
                raise

            except Exception as e:
                last_exception = APIError(f"Unexpected error: {e}")
                logger.exception(f"Unexpected error for {domain}")

            # Wait before retry (exponential backoff with jitter)
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) + (asyncio.get_event_loop().time() % 1)
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        # All retries exhausted
        if last_exception:
            raise last_exception
        raise APIError("Max retries exceeded")

    async def health_check(self) -> bool:
        """Check if API is reachable."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/v1/search", params={"domain": "example.com"}, timeout=10.0)
            return response.status_code == 200
        except Exception:
            return False


# Global client instance (initialized in main.py)
_api_client: Optional[SubdomainAPIClient] = None


def get_api_client() -> SubdomainAPIClient:
    """Get or create the global API client."""
    global _api_client
    if _api_client is None:
        settings = get_settings()
        _api_client = SubdomainAPIClient(
            base_url=settings.api_base_url,
            api_key=settings.api_key,
            timeout=settings.request_timeout,
            cache_ttl=settings.cache_ttl,
            proxy_url=settings.proxy_url,
        )
    return _api_client


async def close_api_client() -> None:
    """Close the global API client."""
    global _api_client
    if _api_client:
        await _api_client.close()
        _api_client = None