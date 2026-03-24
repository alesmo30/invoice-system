import asyncio

from dotenv import load_dotenv

from crud.prisma_crud import PrismaCrudService


async def main() -> None:
    load_dotenv()
    service = PrismaCrudService()
    await service.connect()

    try:
        products = await service.db.product.find_many(order=[{"category": "asc"}, {"name": "asc"}])
        print(f"\n📦 Total products in database: {len(products)}\n")

        current_category = None
        for product in products:
            if product.category != current_category:
                current_category = product.category
                print(f"\n{current_category}:")
                print("-" * 60)

            print(f"  • {product.name:<45} ${product.unit_price:>8.2f}")
            print(f"    SKU: {product.sku}")

        print()

    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
