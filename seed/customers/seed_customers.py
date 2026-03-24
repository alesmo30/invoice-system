import asyncio

from dotenv import load_dotenv

from crud.prisma_crud import PrismaCrudService


async def main() -> None:
    load_dotenv()
    service = PrismaCrudService()
    await service.connect()

    try:
        print("Loading customer seed data...")

        customers = [
            {"first_name": "Sofia", "last_name": "Martinez", "email": "sofia.martinez@example.com", "phone": "+1-555-1001"},
            {"first_name": "Daniel", "last_name": "Garcia", "email": "daniel.garcia@example.com", "phone": "+1-555-1002"},
            {"first_name": "Valentina", "last_name": "Lopez", "email": "valentina.lopez@example.com", "phone": "+1-555-1003"},
            {"first_name": "Mateo", "last_name": "Hernandez", "email": "mateo.hernandez@example.com", "phone": "+1-555-1004"},
            {"first_name": "Camila", "last_name": "Perez", "email": "camila.perez@example.com", "phone": "+1-555-1005"},
            {"first_name": "Santiago", "last_name": "Gonzalez", "email": "santiago.gonzalez@example.com", "phone": "+1-555-1006"},
            {"first_name": "Isabella", "last_name": "Rodriguez", "email": "isabella.rodriguez@example.com", "phone": "+1-555-1007"},
            {"first_name": "Sebastian", "last_name": "Ramirez", "email": "sebastian.ramirez@example.com", "phone": "+1-555-1008"},
            {"first_name": "Mariana", "last_name": "Torres", "email": "mariana.torres@example.com", "phone": "+1-555-1009"},
            {"first_name": "Nicolas", "last_name": "Flores", "email": "nicolas.flores@example.com", "phone": "+1-555-1010"},
            {"first_name": "Lucia", "last_name": "Rivera", "email": "lucia.rivera@example.com", "phone": "+1-555-1011"},
            {"first_name": "Emiliano", "last_name": "Vargas", "email": "emiliano.vargas@example.com", "phone": "+1-555-1012"},
            {"first_name": "Renata", "last_name": "Castro", "email": "renata.castro@example.com", "phone": "+1-555-1013"},
            {"first_name": "Thiago", "last_name": "Mendoza", "email": "thiago.mendoza@example.com", "phone": "+1-555-1014"},
            {"first_name": "Antonella", "last_name": "Silva", "email": "antonella.silva@example.com", "phone": "+1-555-1015"},
        ]

        for customer in customers:
            await service.upsert_customer(**customer)

        print("Successfully loaded 15 customers into the database.")
    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
