import asyncio

from app.database import engine, Base
from app.models.user import User


async def create_tables():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    print("✅ Tables created successfully")


asyncio.run(create_tables())