import asyncio
from bot.database import init_db, get_db, get_user_language, set_user_language

async def test():
    await init_db()
    
    # Test setting and getting language
    await set_user_language(12345, "fa")
    lang = await get_user_language(12345)
    print(f"Language for 12345: {lang}")
    
    # Check tables
    async with get_db() as db:
        cursor = await db.execute('SELECT name FROM sqlite_master WHERE type="table"')
        tables = await cursor.fetchall()
        print('Tables:', tables)
        
        cursor = await db.execute("SELECT * FROM users")
        users = await cursor.fetchall()
        print('Users:', users)

asyncio.run(test())