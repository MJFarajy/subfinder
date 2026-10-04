"""Thin httpx client for Bale Bot API."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union

import httpx

from bot.config import get_settings

logger = logging.getLogger(__name__)


class BaleAPIError(Exception):
    """Bale API error."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        super().__init__(message)
        self.error_code = error_code


class BaleClient:
    """Async client for Bale Bot API."""

    def __init__(
        self,
        token: str,
        timeout: int = 60,
        proxy_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.token = token
        self.base_url = f"https://tapi.bale.ai/bot{token}"
        self.timeout = timeout
        self.proxy_url = proxy_url
        self._client: Optional[httpx.AsyncClient] = client
        self._own_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            if self._own_client:
                transport = httpx.AsyncHTTPTransport(
                    local_address="0.0.0.0",
                    retries=0,
                )
                self._client = httpx.AsyncClient(
                    transport=transport,
                    timeout=httpx.Timeout(self.timeout, connect=30.0, read=self.timeout, write=self.timeout),
                    proxy=self.proxy_url,
                )
            else:
                raise RuntimeError("Client not provided and own client not initialized")
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._own_client and self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        payload: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to Bale API."""
        client = await self._get_client()
        url = f"{self.base_url}/{method}"

        try:
            if files:
                response = await client.post(url, data=payload, files=files)
            else:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            data = response.json()

            if not data.get("ok"):
                error_msg = data.get("description", "Unknown error")
                error_code = data.get("error_code")
                logger.error(f"Bale API error ({method}): {error_code} - {error_msg}")
                raise BaleAPIError(error_msg, error_code)

            return data.get("result", {})

        except httpx.TimeoutException as e:
            logger.warning(f"Bale API timeout ({method}): {e}")
            raise BaleAPIError(f"Request timeout after {self.timeout}s")
        except httpx.NetworkError as e:
            logger.warning(f"Bale API network error ({method}): {e}")
            raise BaleAPIError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Bale API invalid JSON response ({method}): {e}")
            raise BaleAPIError(f"Invalid response: {e}")

    # Bot info
    async def get_me(self) -> Dict[str, Any]:
        """Get bot info."""
        return await self._request("getMe")

    # Messages
    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: Optional[str] = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        """Send a text message."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        return await self._request("sendMessage", payload)

    async def edit_message_text(
        self,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        parse_mode: Optional[str] = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Edit a message text."""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        return await self._request("editMessageText", payload)

    async def send_document(
        self,
        chat_id: Union[int, str],
        document: bytes,
        filename: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = "Markdown",
    ) -> Dict[str, Any]:
        """Send a document."""
        payload = {
            "chat_id": chat_id,
        }
        if caption:
            payload["caption"] = caption
        if parse_mode:
            payload["parse_mode"] = parse_mode

        files = {
            "document": (filename, document, "text/plain"),
        }

        return await self._request("sendDocument", payload, files)

    # Updates
    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 30,
        allowed_updates: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get updates via long polling."""
        payload = {
            "limit": limit,
            "timeout": timeout,
        }
        if offset is not None:
            payload["offset"] = offset
        if allowed_updates:
            payload["allowed_updates"] = json.dumps(allowed_updates)

        result = await self._request("getUpdates", payload)
        return result if isinstance(result, list) else []

    # Callbacks
    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> Dict[str, Any]:
        """Answer a callback query."""
        payload = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text

        return await self._request("answerCallbackQuery", payload)

    # Bot commands
    async def set_my_commands(
        self,
        commands: List[Dict[str, str]],
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set bot commands menu."""
        payload = {
            "commands": json.dumps(commands),
        }
        if language_code:
            payload["language_code"] = language_code

        return await self._request("setMyCommands", payload)

    async def delete_my_commands(
        self,
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete bot commands menu."""
        payload = {}
        if language_code:
            payload["language_code"] = language_code

        return await self._request("deleteMyCommands", payload)