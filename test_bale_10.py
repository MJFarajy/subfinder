#!/usr/bin/env python3
"""Test Bale connectivity with 10 getMe calls."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bot.config import get_settings
from bot.bale_client import BaleClient


async def test_bale_10_times() -> tuple[int, int]:
    """Run getMe 10 times and return (successes, total)."""
    settings = get_settings()
    
    print(f"Testing Bale API with token: {settings.bale_bot_token[:5]}...{settings.bale_bot_token[-3:]}")
    print(f"Running getMe 10 times...\n")

    client = BaleClient(
        token=settings.bale_bot_token,
        timeout=settings.request_timeout,
        proxy_url=settings.proxy_url,
    )

    successes = 0
    failures = 0
    
    for i in range(1, 11):
        try:
            me = await client.get_me()
            print(f"  [{i}/10] OK: @{me.get('username')} (ID: {me.get('id')})")
            successes += 1
        except Exception as e:
            print(f"  [{i}/10] FAIL: {type(e).__name__}: {e}")
            failures += 1
        
        await asyncio.sleep(0.5)

    await client.close()
    return successes, failures


async def main():
    print("=" * 60)
    print("Bale Connectivity Test (10x getMe)")
    print("=" * 60)
    
    successes, failures = await test_bale_10_times()
    
    print("\n" + "=" * 60)
    print(f"Results: {successes}/10 successful, {failures}/10 failed")
    print("=" * 60)
    
    if successes == 10:
        print("ALL TESTS PASSED - Bale connectivity is stable!")
        return 0
    elif successes >= 8:
        print("MOSTLY WORKING - Minor intermittent issues")
        return 0
    else:
        print("CONNECTIVITY ISSUES - Need to fix network")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))