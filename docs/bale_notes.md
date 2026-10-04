# Bale Bot API - Exploration Notes

## Overview
- **Base URL**: `https://tapi.bale.ai/bot<TOKEN>`
- **Authentication**: Token in URL path (no headers needed)
- **Content-Type**: `application/json` for most calls, `multipart/form-data` for file uploads
- **Rate Limits**: Not explicitly documented, but 429 responses observed under heavy load

## API Endpoints Tested

### getMe
- **Method**: POST
- **URL**: `https://tapi.bale.ai/bot<TOKEN>/getMe`
- **Payload**: None
- **Response**: `{"ok": true, "result": {"id": 999049914, "is_bot": true, "first_name": "my_subfinder_bot", "username": "my_subfinder_bot"}}`
- **Notes**: Works reliably, 10/10 successful calls

### getUpdates (Long Polling)
- **Method**: POST
- **URL**: `https://tapi.bale.ai/bot<TOKEN>/getUpdates`
- **Payload**: `{"offset": 0, "limit": 100, "timeout": 30, "allowed_updates": ["message", "callback_query"]}`
- **Response**: `{"ok": true, "result": []}` (empty array when no updates)
- **Timeout**: Server holds connection for up to `timeout` seconds (30s tested)
- **Notes**: Works well for long polling, returns empty array when no updates

### sendMessage
- **Method**: POST
- **URL**: `https://tapi.bale.ai/bot<TOKEN>/sendMessage`
- **Payload**: 
  ```json
  {
    "chat_id": 123456789,
    "text": "Hello",
    "parse_mode": "Markdown",
    "disable_web_page_preview": true,
    "reply_markup": "{\"inline_keyboard\": [[{\"text\": \"Btn\", \"callback_data\": \"data\"}]]}"
  }
  ```
- **Response**: `{"ok": true, "result": {"message_id": 1, "chat": {"id": 123}, "date": 1234567890}}`
- **Parse Modes**: "Markdown" supported (no HTML support confirmed)
- **Error**: 400 "Bad Request: no such group or user" for invalid chat_id
- **Notes**: `reply_markup` must be JSON-encoded string

### editMessageText
- **Method**: POST
- **URL**: `https://tapi.bale.ai/bot<TOKEN>/editMessageText`
- **Payload**: 
  ```json
  {
    "chat_id": 123456789,
    "message_id": 1,
    "text": "Edited text",
    "parse_mode": "Markdown"
  }
  ```
- **Response**: `{"ok": true, "result": true}`
- **Notes**: Works for editing bot's own messages

### sendDocument
- **Method**: POST
- **URL**: `https://tapi.bale.ai/bot<TOKEN>/sendDocument`
- **Payload**: multipart/form-data with `chat_id`, optional `caption`, `parse_mode`, and `document` file
- **Response**: `{"ok": true, "result": {"message_id": 1, ...}}`
- **Notes**: Works for sending .txt files

### answerCallbackQuery
- **Method**: POST
- **URL**: `https://tapi.bale.ai/bot<TOKEN>/answerCallbackQuery`
- **Payload**: `{"callback_query_id": "abc123", "text": "Toast message", "show_alert": true}`
- **Response**: `{"ok": true, "result": true}`
- **Notes**: Shows toast notification to user

### setMyCommands
- **Method**: POST
- **URL**: `https://tapi.bale.ai/bot<TOKEN>/setMyCommands`
- **Payload**: `{"commands": "[{\"command\": \"start\", \"description\": \"Start\"}]", "language_code": "en"}`
- **Response**: `{"ok": true, "result": true}`
- **Notes**: Supports `language_code` parameter for localization (tested with "en" and "fa")

## Differences from Telegram Bot API

| Feature | Telegram | Bale |
|---------|----------|------|
| Base URL | `https://api.telegram.org/bot<TOKEN>` | `https://tapi.bale.ai/bot<TOKEN>` |
| Auth | Token in header or URL | Token in URL path only |
| Parse Modes | Markdown, MarkdownV2, HTML | Markdown only (HTML not confirmed) |
| Callback Data Limit | 64 bytes | Likely same (not explicitly documented) |
| Message Length Limit | 4096 chars | Similar (assumed ~4000 for safety) |
| File Size Limit | 50 MB | Not explicitly documented |
| Bot Commands Menu | Yes, with language_code | Yes, with language_code |
| User Language Code | Available in `from.language_code` | Not available in updates |
| Long Polling Timeout | Up to 1000s | Up to 30s tested (likely similar) |
| IPv6 Support | Yes | Not tested (IPv4 forced) |
| Proxy Support | Via aiohttp-socks | Same (httpx supports proxies) |

## Network Behavior (Tested from Iran)
- **Direct connection**: Works without VPN/proxy
- **No filtering**: Bale API is accessible from Iran
- **Latency**: ~1-2 seconds for getMe
- **Reliability**: 10/10 getMe calls successful
- **Long Polling**: Stable, no disconnections observed during 3+ minute test

## Message Length Limits
- **Assumed**: ~4000 characters (same safety margin as Telegram)
- **File fallback**: Send as .txt when exceeding limit
- **Code blocks**: Use Markdown triple backticks for subdomain lists to prevent RTL scrambling

## Implementation Notes

### BaleClient Design
- Custom httpx-based client (no third-party library dependency)
- Supports proxy via httpx proxy parameter
- Forces IPv4 via `local_address="0.0.0.0"`
- Injectable client for testing
- Proper timeout configuration (connect=30s, read=60s, write=60s)

### Long Polling Implementation
```python
updates = await client.get_updates(
    offset=offset,
    limit=100,
    timeout=30,
    allowed_updates=["message", "callback_query"],
)
```
- `timeout=30` means server holds connection for 30s waiting for updates
- `offset` tracks processed updates
- `allowed_updates` reduces payload size

### Error Handling
- `BaleAPIError` wraps all API errors with `error_code`
- Network errors caught and retried with exponential backoff
- Global error handler logs but never crashes the bot

### Language Support
- Default fallback: Persian (FA) since Bale users are primarily Persian-speaking
- Telegram's `language_code` not available in Bale updates
- Language selection via inline keyboard works identically to Telegram version

### Missing Telegram Features (Not Implemented)
- Webhook support (long polling only)
- Inline queries
- Payment API
- Passport API
- Games API

## Testing Results
- **getMe**: 10/10 successful
- **sendMessage**: Works (fails with 400 for invalid chat_id as expected)
- **getUpdates**: Works (returns empty array when no updates)
- **setMyCommands**: Works for both "en" and "fa"
- **editMessageText**: Works
- **sendDocument**: Works for .txt files
- **answerCallbackQuery**: Works
- **Long Polling**: Stable for 3+ minutes without errors

## Configuration
```env
PLATFORM=bale
BALE_BOT_TOKEN=your_token_here
REQUEST_TIMEOUT=60
RATE_LIMIT_SECONDS=3
PROXY_URL=  # Optional, not needed for Bale from Iran
```

## Command to Run
```bash
cd C:\Users\mj\projects\subfinder
venv\Scripts\python -m bot.bale_main
```

## Conclusion
Bale Bot API is a near-complete subset of Telegram Bot API with Markdown-only formatting. It works reliably from Iran without VPN/proxy. The custom BaleClient provides all needed functionality with proper error handling, retries, and testability.