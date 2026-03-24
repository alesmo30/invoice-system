import asyncio

from dotenv import load_dotenv

from crud.prisma_crud import PrismaCrudService


async def main() -> None:
    load_dotenv()
    service = PrismaCrudService()
    await service.connect()

    try:
        print("Loading employee seed data...")

        employees = [
            {
                "first_name": "Alejandro",
                "last_name": "Morales",
                "email": "alejandro.morales@apple-retail.local",
            },
            {
                "first_name": "Camila",
                "last_name": "Ruiz",
                "email": "camila.ruiz@apple-retail.local",
            },
            {
                "first_name": "Diego",
                "last_name": "Fernandez",
                "email": "diego.fernandez@apple-retail.local",
            },
            {
                "first_name": "Valeria",
                "last_name": "Soto",
                "email": "valeria.soto@apple-retail.local",
            },
            {
                "first_name": "Mateo",
                "last_name": "Vargas",
                "email": "mateo.vargas@apple-retail.local",
            },
        ]

        for employee in employees:
            await service.upsert_employee(**employee)

        print("Successfully loaded 5 employees into the database.")
    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
