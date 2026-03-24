import asyncio
from decimal import Decimal

from dotenv import load_dotenv

from crud.prisma_crud import PrismaCrudService


async def main() -> None:
    load_dotenv()
    service = PrismaCrudService()
    await service.connect()

    try:
        print("Loading Apple product inventory...")

        # Mac lineup
        await service.upsert_product(
            name="MacBook Neo 13-inch",
            category="Mac",
            sku="MACBOOK-NEO-13",
            unit_price=Decimal("599.00"),
        )
        await service.upsert_product(
            name="MacBook Air M5 13-inch 512GB",
            category="Mac",
            sku="MBA-M5-13-512",
            unit_price=Decimal("1199.00"),
        )
        await service.upsert_product(
            name="MacBook Air M5 15-inch 512GB",
            category="Mac",
            sku="MBA-M5-15-512",
            unit_price=Decimal("1499.00"),
        )
        await service.upsert_product(
            name="MacBook Pro M5 Pro 14-inch 1TB",
            category="Mac",
            sku="MBP-M5PRO-14-1TB",
            unit_price=Decimal("1999.00"),
        )
        await service.upsert_product(
            name="MacBook Pro M5 Max 16-inch 2TB",
            category="Mac",
            sku="MBP-M5MAX-16-2TB",
            unit_price=Decimal("2999.00"),
        )

        # iPhone lineup
        await service.upsert_product(
            name="iPhone 17e 256GB",
            category="iPhone",
            sku="IPHONE-17E-256",
            unit_price=Decimal("599.00"),
        )
        await service.upsert_product(
            name="iPhone 17 256GB",
            category="iPhone",
            sku="IPHONE-17-256",
            unit_price=Decimal("829.00"),
        )
        await service.upsert_product(
            name="iPhone 17 512GB",
            category="iPhone",
            sku="IPHONE-17-512",
            unit_price=Decimal("1029.00"),
        )
        await service.upsert_product(
            name="iPhone 17 Pro 256GB",
            category="iPhone",
            sku="IPHONE-17PRO-256",
            unit_price=Decimal("1199.00"),
        )
        await service.upsert_product(
            name="iPhone 17 Pro Max 1TB",
            category="iPhone",
            sku="IPHONE-17PROMAX-1TB",
            unit_price=Decimal("1599.00"),
        )

        # iPad lineup
        await service.upsert_product(
            name="iPad 11-inch 128GB Wi-Fi",
            category="iPad",
            sku="IPAD-11-128-WIFI",
            unit_price=Decimal("349.00"),
        )
        await service.upsert_product(
            name="iPad Air M4 11-inch 256GB",
            category="iPad",
            sku="IPAD-AIR-M4-11-256",
            unit_price=Decimal("749.00"),
        )
        await service.upsert_product(
            name="iPad Pro M5 13-inch 512GB",
            category="iPad",
            sku="IPAD-PRO-M5-13-512",
            unit_price=Decimal("1299.00"),
        )

        # AirPods lineup
        await service.upsert_product(
            name="AirPods Pro 3",
            category="Accessories",
            sku="AIRPODS-PRO-3",
            unit_price=Decimal("249.00"),
        )
        await service.upsert_product(
            name="AirPods Max 2",
            category="Accessories",
            sku="AIRPODS-MAX-2",
            unit_price=Decimal("549.00"),
        )

        print("✅ Successfully loaded 15 Apple products into the database.")

    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
