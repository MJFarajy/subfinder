"""Unit tests for Bale client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from bot.bale_client import BaleClient, BaleAPIError


class TestBaleClient:
    """Tests for BaleClient."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        mock = AsyncMock(spec=httpx.AsyncClient)
        mock.is_closed = False
        return mock

    @pytest.fixture
    def client(self, mock_httpx_client):
        return BaleClient(
            token="test_token",
            timeout=30,
            proxy_url=None,
            client=mock_httpx_client,
        )

    @pytest.mark.asyncio
    async def test_get_me_success(self, client, mock_httpx_client):
        """Test successful getMe call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"id": 123, "username": "test_bot", "first_name": "Test Bot"}
        }
        mock_httpx_client.post.return_value = mock_response

        result = await client.get_me()

        assert result["id"] == 123
        assert result["username"] == "test_bot"
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_me_api_error(self, client, mock_httpx_client):
        """Test getMe with API error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 401,
            "description": "Unauthorized"
        }
        mock_httpx_client.post.return_value = mock_response

        with pytest.raises(BaleAPIError) as exc_info:
            await client.get_me()

        assert exc_info.value.error_code == 401
        assert "Unauthorized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_me_timeout(self, client, mock_httpx_client):
        """Test getMe with timeout."""
        mock_httpx_client.post.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(BaleAPIError) as exc_info:
            await client.get_me()

        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_send_message_success(self, client, mock_httpx_client):
        """Test successful sendMessage."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 1, "chat": {"id": 123}}
        }
        mock_httpx_client.post.return_value = mock_response

        result = await client.send_message(chat_id=123, text="Hello")

        assert result["message_id"] == 1
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert "sendMessage" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["chat_id"] == 123
        assert payload["text"] == "Hello"
        assert payload["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_send_message_with_keyboard(self, client, mock_httpx_client):
        """Test sendMessage with inline keyboard."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 1}
        }
        mock_httpx_client.post.return_value = mock_response

        keyboard = {"inline_keyboard": [[{"text": "Test", "callback_data": "test"}]]}
        await client.send_message(chat_id=123, text="Hello", reply_markup=keyboard)

        call_args = mock_httpx_client.post.call_args
        payload = call_args[1]["json"]
        assert "reply_markup" in payload
        import json
        markup = json.loads(payload["reply_markup"])
        assert markup == keyboard

    @pytest.mark.asyncio
    async def test_edit_message_text(self, client, mock_httpx_client):
        """Test editMessageText."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": True
        }
        mock_httpx_client.post.return_value = mock_response

        result = await client.edit_message_text(chat_id=123, message_id=1, text="Edited")

        assert result is True

    @pytest.mark.asyncio
    async def test_send_document(self, client, mock_httpx_client):
        """Test sendDocument."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 1}
        }
        mock_httpx_client.post.return_value = mock_response

        result = await client.send_document(
            chat_id=123,
            document=b"test content",
            filename="test.txt",
            caption="Test file"
        )

        assert result["message_id"] == 1
        call_args = mock_httpx_client.post.call_args
        assert "files" in call_args[1]

    @pytest.mark.asyncio
    async def test_get_updates(self, client, mock_httpx_client):
        """Test getUpdates."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {"update_id": 1, "message": {"message_id": 1}},
                {"update_id": 2, "message": {"message_id": 2}},
            ]
        }
        mock_httpx_client.post.return_value = mock_response

        updates = await client.get_updates(offset=0, limit=100, timeout=30)

        assert len(updates) == 2
        assert updates[0]["update_id"] == 1
        assert updates[1]["update_id"] == 2

    @pytest.mark.asyncio
    async def test_answer_callback_query(self, client, mock_httpx_client):
        """Test answerCallbackQuery."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": True
        }
        mock_httpx_client.post.return_value = mock_response

        result = await client.answer_callback_query("callback_123", "Test", show_alert=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_my_commands(self, client, mock_httpx_client):
        """Test setMyCommands."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": True
        }
        mock_httpx_client.post.return_value = mock_response

        commands = [{"command": "start", "description": "Start"}]
        result = await client.set_my_commands(commands, language_code="en")

        assert result is True

    @pytest.mark.asyncio
    async def test_close(self, client, mock_httpx_client):
        """Test close - should not close injected client."""
        await client.close()
        # Should not call aclose on injected client
        mock_httpx_client.aclose.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])