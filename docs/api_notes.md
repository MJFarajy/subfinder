# AgniOps Subdomain Finder API - Exploration Notes

## Overview
- **Base URL**: `https://app.agniops.in`
- **Search Endpoint**: `GET /v1/search?domain=<DOMAIN>`
- **Authentication**: None required (works without API key)
- **Rate Limit**: 60 requests/minute (enforced via headers)

## Response Format

### Success (200 OK)
- **Content-Type**: `text/plain; charset=utf-8`
- **Body**: Plain text, one subdomain per line
- **Example**:
  ```
  autodiscover.example.com
  ct-test.example.com
  demo.example.com
  ...
  ```

### Error Responses

#### 400 Bad Request - Invalid Domain
```json
{
  "error": "INVALID_DOMAIN",
  "message": "Please specify a valid fully-qualified domain name (e.g. example.com)."
}
```

#### 429 Too Many Requests - Rate Limited
```
Free search limit reached or backend provider temporarily busy. Please log in or sign up at /login to continue scanning without limits.
URL: /login
```
- Headers may include `retry-after` (seconds)

#### 401 Unauthorized
- Not observed during testing (no auth required)

#### 403 Forbidden
- Not observed during testing

## Headers (Success Response)
```
x-ratelimit-limit: 60
x-ratelimit-remaining: 59
x-ratelimit-reset: 1791021376
content-type: text/plain; charset=utf-8
server: cloudflare
```

## Rate Limiting
- **Limit**: 60 requests per minute
- **Headers**: `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`
- **Reset**: Unix timestamp when limit resets

## Observations

### Example.com Test
- **Status**: 200
- **Subdomains found**: 4,017
- **Response time**: ~1-2 seconds

### Github.com Test
- **Status**: 200
- **Subdomains found**: 52,524
- **Response time**: ~3-5 seconds (larger result set)
- **Note**: Very large response, may need longer timeout

### Non-existent Domain Test
- **Status**: 429 (not 404)
- **Message**: "Free search limit reached or backend provider temporarily busy..."
- **Note**: API returns 429 for domains with no results or when free tier limit reached

## Documentation Endpoints
- `/docs` - Returns HTML documentation page (200)
- `/openapi.json` - Returns 404 (no OpenAPI spec)
- `/v1` - Returns 404 (no root endpoint)

## Implementation Notes for Bot

1. **Timeout**: Use generous timeout (60s) for large domains like github.com
2. **Parsing**: Split response by newline, filter empty lines
3. **Caching**: Cache results for ~10 minutes (TTL) to avoid repeated API calls
4. **Rate Limiting**: 
   - Respect `x-ratelimit-remaining` header
   - Implement per-user rate limiting (3 seconds between requests)
   - Handle 429 with retry-after header
5. **Error Handling**:
   - 400 → Invalid domain error
   - 429 → Rate limit error (show retry-after)
   - Timeout → Retry with exponential backoff (max 3 retries)
   - Network errors → Retry with backoff
6. **No API Key Needed**: The API works without authentication

## Test Results Summary

| Domain | Status | Subdomains | Response Time |
|--------|--------|------------|---------------|
| example.com | 200 | 4,017 | ~1.5s |
| github.com | 200 | 52,524 | ~4s |
| invalid..domain | 400 | N/A | ~0.5s |
| nonexistent12345.com | 429 | N/A | ~1s |

## Recommendations

1. Set `REQUEST_TIMEOUT=60` or higher for large domains
2. Implement client-side caching (10 min TTL)
3. Handle 429 gracefully with user-friendly message
4. Parse plain text response line by line
5. Deduplicate and sort subdomains before presenting to user