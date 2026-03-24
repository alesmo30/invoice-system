import asyncio

from dotenv import load_dotenv
from prisma import Prisma


async def main() -> None:
    load_dotenv()
    db = Prisma()
    await db.connect()

    # Simple connectivity check against PostgreSQL.
    result = await db.query_first("SELECT current_database() AS db_name, now() AS server_time;")
    print("Prisma connection successful.")
    print(result)

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
