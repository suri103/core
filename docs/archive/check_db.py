import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine("sqlite+aiosqlite:///./test_conn.db")
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        print("Connection successful")

if __name__ == "__main__":
    asyncio.run(check())
