import asyncio
from datetime import date
from decimal import Decimal

from dotenv import load_dotenv

from crud.prisma_crud import InvoiceItemInput, PrismaCrudService


async def main() -> None:
    load_dotenv()
    service = PrismaCrudService()
    await service.connect()

    try:
        # 1) Employees
        alex = await service.upsert_employee(
            first_name="Alex",
            last_name="Rivera",
            email="alex.rivera@apple-retail.local",
        )
        nina = await service.upsert_employee(
            first_name="Nina",
            last_name="Lopez",
            email="nina.lopez@apple-retail.local",
        )

        # 2) Customers
        customer_1 = await service.upsert_customer(
            first_name="Sofia",
            last_name="Martinez",
            email="sofia.martinez@example.com",
            phone="+1-555-0101",
        )
        customer_2 = await service.upsert_customer(
            first_name="Daniel",
            last_name="Garcia",
            email="daniel.garcia@example.com",
            phone="+1-555-0102",
        )

        # 3) Products
        iphone = await service.upsert_product(
            name="iPhone 15 Pro 256GB",
            category="iPhone",
            sku="IPHONE-15-PRO-256",
            unit_price=Decimal("1099.00"),
        )
        macbook = await service.upsert_product(
            name="MacBook Pro M3 14-inch",
            category="Mac",
            sku="MBP-M3-14",
            unit_price=Decimal("1999.00"),
        )
        airpods = await service.upsert_product(
            name="AirPods Pro (2nd Gen)",
            category="Accessories",
            sku="AIRPODS-PRO-2",
            unit_price=Decimal("249.00"),
        )

        # 4) Invoices + items
        await service.create_invoice(
            invoice_number="INV-2026-0001",
            employee_id=alex.id,
            customer_id=customer_1.id,
            invoice_date=date(2026, 3, 20),
            items=[
                InvoiceItemInput(product_id=iphone.id, quantity=1, unit_price=Decimal("1099.00")),
                InvoiceItemInput(product_id=airpods.id, quantity=1, unit_price=Decimal("249.00")),
            ],
        )
        await service.create_invoice(
            invoice_number="INV-2026-0002",
            employee_id=nina.id,
            customer_id=customer_2.id,
            invoice_date=date(2026, 3, 21),
            items=[
                InvoiceItemInput(product_id=macbook.id, quantity=1, unit_price=Decimal("1999.00")),
            ],
        )

        invoices = await service.list_invoices()
        print("Seed loaded successfully.")
        print(f"Current invoices in DB: {len(invoices)}")
    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
