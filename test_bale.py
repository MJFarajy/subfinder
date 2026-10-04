#!/usr/bin/env python3
"""Test Bale client with real API calls."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bot.config import get_settings
from bot.bale_client import BaleClient


async def test_bale():
    settings = get_settings()
    print(f"Testing Bale API with token: {settings.bale_bot_token[:5]}...{settings.bale_bot_token[-3:]}")

    client = BaleClient(
        token=settings.bale_bot_token,
        timeout=settings.request_timeout,
        proxy_url=settings.proxy_url,
    )

    try:
        # Test getMe
        print("\n1. Testing getMe...")
        me = await client.get_me()
        print(f"   OK: @{me.get('username')} (ID: {me.get('id')})")

        # Test sendMessage (will fail with invalid chat_id but should not timeout)
        print("\n2. Testing sendMessage (expected to fail with 400)...")
        try:
            await client.send_message(chat_id=123456789, text="test")
            print("   Unexpected success")
        except Exception as e:
            print(f"   Expected error: {e}")

        # Test getUpdates (short timeout)
        print("\n3. Testing getUpdates (timeout=2)...")
        updates = await client.get_updates(timeout=2)
        print(f"   OK: {len(updates)} updates")

        # Test setMyCommands
        print("\n4. Testing setMyCommands...")
        commands = [
            {"command": "start", "description": "Start the bot"},
            {"command": "help", "description": "Show help"},
            {"command": "language", "description": "Change language"},
        ]
        try:
            result = await client.set_my_commands(commands)
            print(f"   OK: {result}")
        except Exception as e:
            print(f"   Error: {e}")

    finally:
        await client.close()

    print("\nAll tests completed!")


if __name__ == "__main__":
    asyncio.run(test_bale())