import asyncio

from dotenv import load_dotenv

from crud.prisma_crud import PrismaCrudService


async def main() -> None:
    load_dotenv()
    service = PrismaCrudService()
    await service.connect()

    try:
        employees = await service.db.employee.find_many(
            order=[{"last_name": "asc"}, {"first_name": "asc"}]
        )
        print(f"Total employees in database: {len(employees)}")
        print("-" * 60)
        for employee in employees:
            print(f"- {employee.first_name} {employee.last_name}")
            print(f"  Email: {employee.email}")
            print(f"  ID: {employee.id}")
        print("-" * 60)
    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
