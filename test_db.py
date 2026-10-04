import asyncio
from bot.database import init_db, get_db

async def test():
    await init_db()
    async with get_db() as db:
        cursor = await db.execute('SELECT name FROM sqlite_master WHERE type="table"')
        tables = await cursor.fetchall()
        print('Tables:', tables)

asyncio.run(test())