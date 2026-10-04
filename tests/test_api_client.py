"""Unit tests for API client and response parsing."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from bot.api_client import (
    APIError,
    AuthenticationError,
    ForbiddenError,
    InvalidDomainError,
    RateLimitError,
    SubdomainAPIClient,
    TimeoutError,
)
from bot.cache import _memory_cache, CACHE_FILE


class TestSubdomainAPIClient:
    """Tests for SubdomainAPIClient."""

    @pytest.fixture
    def client(self):
        return SubdomainAPIClient(
            base_url="https://api.example.com",
            api_key="test-key",
            timeout=30,
            cache_ttl=600,
            bypass_rate_limit=True,
        )

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear memory and disk cache before each test."""
        _memory_cache.clear()
        # Clear disk cache
        import os
        if CACHE_FILE.exists():
            os.remove(CACHE_FILE)
        yield
        _memory_cache.clear()
        if CACHE_FILE.exists():
            os.remove(CACHE_FILE)

    @pytest.fixture
    def mock_response(self):
        def _make_response(status_code: int, text: str, headers: dict = None):
            response = MagicMock(spec=httpx.Response)
            response.status_code = status_code
            response.text = text
            response.headers = headers or {"content-type": "text/plain"}
            response.json = MagicMock(side_effect=lambda: {"error": "TEST_ERROR", "message": text})
            return response
        return _make_response

    @pytest.mark.asyncio
    async def test_parse_plain_text_response(self, client, mock_response):
        """Test parsing plain text response (one subdomain per line)."""
        response = mock_response(200, "sub1.example.com\nsub2.example.com\nsub3.example.com")
        subdomains, headers = client._parse_response(response)
        assert subdomains == ["sub1.example.com", "sub2.example.com", "sub3.example.com"]

    @pytest.mark.asyncio
    async def test_parse_empty_response(self, client, mock_response):
        """Test parsing empty response."""
        response = mock_response(200, "")
        subdomains, headers = client._parse_response(response)
        assert subdomains == []

    @pytest.mark.asyncio
    async def test_parse_response_with_whitespace(self, client, mock_response):
        """Test parsing response with extra whitespace."""
        response = mock_response(200, "  sub1.example.com  \n\n  sub2.example.com  \n")
        subdomains, headers = client._parse_response(response)
        assert subdomains == ["sub1.example.com", "sub2.example.com"]

    @pytest.mark.asyncio
    async def test_parse_json_error_response(self, client, mock_response):
        """Test parsing JSON error response - JSON errors are handled in search(), not _parse_response()."""
        # _parse_response catches JSON parse errors and falls back to text parsing
        # This test verifies the fallback behavior
        response = mock_response(400, '{"error": "INVALID_DOMAIN", "message": "Invalid domain"}')
        response.headers = {"content-type": "application/json"}
        # Should not raise, should fall back to text parsing (returns the JSON as a single "subdomain")
        subdomains, headers = client._parse_response(response)
        # The JSON text becomes one "subdomain" line
        assert len(subdomains) == 1
        assert "INVALID_DOMAIN" in subdomains[0]

    @pytest.mark.asyncio
    async def test_search_success(self, client):
        """Test successful search."""
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "sub1.example.com\nsub2.example.com"
        mock_response.headers = {"content-type": "text/plain"}
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.search("example.com")
            assert result == ["sub1.example.com", "sub2.example.com"]

    @pytest.mark.asyncio
    async def test_search_invalid_domain(self, client):
        """Test search with invalid domain (400)."""
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = '{"error": "INVALID_DOMAIN", "message": "Invalid domain"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = MagicMock(return_value={"error": "INVALID_DOMAIN", "message": "Invalid domain"})
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(InvalidDomainError):
                await client.search("invalid..domain")

    @pytest.mark.asyncio
    async def test_search_rate_limited(self, client):
        """Test search when rate limited (429)."""
        class MockResponse:
            status_code = 429
            text = "Rate limit exceeded"
            headers = {"content-type": "text/plain", "retry-after": "60"}
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MockResponse())

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(RateLimitError) as exc_info:
                await client.search("ratelimited.example.com")
            assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_search_unauthorized(self, client):
        """Test search with invalid API key (401)."""
        class MockResponse:
            status_code = 401
            text = "Unauthorized"
            headers = {"content-type": "text/plain"}
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MockResponse())

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(AuthenticationError):
                await client.search("unauthorized.example.com")

    @pytest.mark.asyncio
    async def test_search_forbidden(self, client):
        """Test search when forbidden (403)."""
        class MockResponse:
            status_code = 403
            text = "Forbidden"
            headers = {"content-type": "text/plain"}
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MockResponse())

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(ForbiddenError):
                await client.search("forbidden.example.com")

    @pytest.mark.asyncio
    async def test_search_timeout_retry(self, client):
        """Test search with timeout and retry."""
        success_response = type('MockResponse', (), {
            'status_code': 200,
            'text': "sub.retry.example.com",
            'headers': {"content-type": "text/plain"}
        })()
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[
            httpx.TimeoutException("Timeout"),
            httpx.TimeoutException("Timeout"),
            success_response,
        ])

        with patch.object(client, "_get_client", return_value=mock_client):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await client.search("retry.example.com", max_retries=3, base_delay=0.01)
                assert result == ["sub.retry.example.com"]

    @pytest.mark.asyncio
    async def test_search_max_retries_exceeded(self, client):
        """Test search when max retries exceeded."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with patch.object(client, "_get_client", return_value=mock_client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(TimeoutError):
                    await client.search("maxretries.example.com", max_retries=2, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_cache_hit(self, client):
        """Test cache returns cached result."""
        # Use the new cache system
        from bot.cache import set_cache, _memory_cache
        # Manually set memory cache for testing
        _memory_cache["example.com"] = (time.time(), ["cached.sub.example.com"])
        
        with patch.object(client, "_get_client", return_value=AsyncMock()):
            result = await client.search("example.com")
            assert result == ["cached.sub.example.com"]

    @pytest.mark.asyncio
    async def test_cache_expiry(self, client):
        """Test expired cache is not used."""
        from bot.cache import _memory_cache
        # Set expired cache
        _memory_cache["example.com"] = (time.time() - 1000, ["old.sub.example.com"])
        
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "new.sub.example.com"
        mock_response.headers = {"content-type": "text/plain"}
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.search("example.com")
            # Should get new result, not expired cache
            assert result == ["new.sub.example.com"]

    @pytest.mark.asyncio
    async def test_close_client(self, client):
        """Test closing the HTTP client."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        client._client = mock_client

        await client.close()
        mock_client.aclose.assert_called_once()