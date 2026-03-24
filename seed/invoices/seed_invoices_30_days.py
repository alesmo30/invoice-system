import asyncio
import random
from datetime import date, timedelta
from decimal import Decimal

from dotenv import load_dotenv

from crud.prisma_crud import InvoiceItemInput, PrismaCrudService


# Popular product combinations (realistic purchase patterns at Apple store)
PRODUCT_BUNDLES = [
    # Single device purchases (most common)
    {"skus": ["IPHONE-17E-256"], "weights": [1]},
    {"skus": ["IPHONE-17-256"], "weights": [1]},
    {"skus": ["IPHONE-17-512"], "weights": [1]},
    {"skus": ["IPHONE-17PRO-256"], "weights": [1]},
    {"skus": ["IPHONE-17PROMAX-1TB"], "weights": [1]},
    {"skus": ["MBA-M5-13-512"], "weights": [1]},
    {"skus": ["MBA-M5-15-512"], "weights": [1]},
    {"skus": ["MBP-M5PRO-14-1TB"], "weights": [1]},
    {"skus": ["MBP-M5MAX-16-2TB"], "weights": [1]},
    {"skus": ["IPAD-11-128-WIFI"], "weights": [1]},
    {"skus": ["IPAD-AIR-M4-11-256"], "weights": [1]},
    {"skus": ["IPAD-PRO-M5-13-512"], "weights": [1]},
    {"skus": ["MACBOOK-NEO-13"], "weights": [1]},
    
    # Accessories alone
    {"skus": ["AIRPODS-PRO-3"], "weights": [1]},
    {"skus": ["AIRPODS-MAX-2"], "weights": [1]},
    {"skus": ["AIRPODS-PRO-2"], "weights": [1]},
    
    # Device + Accessories (common bundles)
    {"skus": ["IPHONE-17-256", "AIRPODS-PRO-3"], "weights": [1, 1]},
    {"skus": ["IPHONE-17PRO-256", "AIRPODS-PRO-3"], "weights": [1, 1]},
    {"skus": ["IPAD-AIR-M4-11-256", "AIRPODS-MAX-2"], "weights": [1, 1]},
    {"skus": ["MBA-M5-13-512", "AIRPODS-PRO-3"], "weights": [1, 1]},
    
    # Multiple accessories
    {"skus": ["AIRPODS-PRO-3", "AIRPODS-PRO-2"], "weights": [1, 2]},
    {"skus": ["AIRPODS-MAX-2", "AIRPODS-PRO-3"], "weights": [1, 1]},
]


async def get_seeded_data(service: PrismaCrudService):
    """Fetch all seeded employees, customers, and products."""
    employees = await service.db.employee.find_many()
    customers = await service.db.customer.find_many()
    products = await service.db.product.find_many()
    
    # Create lookup by SKU for quick access
    sku_map = {p.sku: p for p in products}
    
    return employees, customers, sku_map


def generate_invoice_items(sku_map: dict) -> list[InvoiceItemInput]:
    """Generate a realistic bundle of invoice items."""
    bundle = random.choice(PRODUCT_BUNDLES)
    items = []
    
    for sku, weight in zip(bundle["skus"], bundle["weights"]):
        if sku in sku_map:
            product = sku_map[sku]
            # Quantity: accessories often bought in multiples, devices usually 1
            quantity = random.randint(1, weight + 2) if "AIRPODS" in sku else weight
            items.append(
                InvoiceItemInput(
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=product.unit_price,
                )
            )
    
    return items


async def seed_30_days(service: PrismaCrudService) -> None:
    """Generate 30 days of invoices (8-10 per day)."""
    employees, customers, sku_map = await get_seeded_data(service)
    
    if not employees or not customers or not sku_map:
        print("❌ Error: Could not fetch seeded data. Please run employee, customer, and product seeds first.")
        return
    
    # Find the highest existing invoice number to avoid duplicates
    existing_invoices = await service.db.invoice.find_many(
        where={"invoice_number": {"startswith": "INV-2026-"}},
        order=[{"invoice_number": "desc"}],
        take=1
    )
    
    if existing_invoices:
        # Extract number from "INV-2026-00123" format
        last_number = existing_invoices[0].invoice_number.split("-")[-1]
        invoice_counter = int(last_number) + 1
        print(f"Found existing invoices. Starting from invoice #{invoice_counter:05d}")
    else:
        invoice_counter = 1
        print("No existing invoices found. Starting from invoice #00001")
    
    start_date = date(2026, 3, 1)
    
    print("Generating 30 days of invoice transactions...")
    
    for day_offset in range(30):
        current_date = start_date + timedelta(days=day_offset)
        invoices_today = random.randint(8, 10)
        
        for _ in range(invoices_today):
            invoice_number = f"INV-2026-{invoice_counter:05d}"
            employee = random.choice(employees)
            customer = random.choice(customers)
            items = generate_invoice_items(sku_map)
            
            await service.create_invoice(
                invoice_number=invoice_number,
                employee_id=employee.id,
                customer_id=customer.id,
                invoice_date=current_date,
                items=items,
            )
            
            invoice_counter += 1
        
        print(f"  ✓ {current_date.strftime('%Y-%m-%d')}: {invoices_today} invoices")
    
    total_invoices = invoice_counter - 1
    print(f"\n✅ Successfully generated {total_invoices} invoices over 30 days.")


async def main() -> None:
    load_dotenv()
    service = PrismaCrudService()
    await service.connect()

    try:
        await seed_30_days(service)
    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
