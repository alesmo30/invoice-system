import asyncio
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from crud.prisma_crud import PrismaCrudService


def serialize_invoice_data(invoice) -> dict:
    """Convert invoice data to JSON-serializable format."""
    return {
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.strftime("%Y-%m-%d"),
        "total_amount": str(invoice.total_amount),
        "created_at": invoice.created_at.isoformat(),
        "employee": {
            "id": invoice.employee.id,
            "first_name": invoice.employee.first_name,
            "last_name": invoice.employee.last_name,
            "email": invoice.employee.email,
            "created_at": invoice.employee.created_at.isoformat(),
        } if invoice.employee else None,
        "customer": {
            "id": invoice.customer.id,
            "first_name": invoice.customer.first_name,
            "last_name": invoice.customer.last_name,
            "email": invoice.customer.email,
            "phone": invoice.customer.phone,
            "created_at": invoice.customer.created_at.isoformat(),
        } if invoice.customer else None,
        "items": [
            {
                "id": item.id,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "line_total": str(item.line_total),
                "created_at": item.created_at.isoformat(),
                "product": {
                    "id": item.product.id,
                    "name": item.product.name,
                    "category": item.product.category,
                    "sku": item.product.sku,
                    "unit_price": str(item.product.unit_price),
                    "created_at": item.product.created_at.isoformat(),
                } if item.product else None,
            }
            for item in invoice.items
        ],
    }


async def generate_daily_invoice_json(service: PrismaCrudService, output_dir: str = "seed/invoices/daily_data") -> dict[str, int]:
    """
    Generate JSON files for each day containing all invoices.
    
    Returns a dictionary with statistics about the generation process.
    """
    first_date, last_date = await service.get_invoice_date_range()
    
    if not first_date or not last_date:
        print("❌ No invoices found in the database.")
        return {"files_created": 0, "total_invoices": 0}
    
    print(f"📅 Invoice date range: {first_date} to {last_date}")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    current_date = first_date
    files_created = 0
    total_invoices = 0
    
    while current_date <= last_date:
        invoices = await service.get_invoices_by_date(current_date)
        
        if invoices:
            daily_data = {}
            for invoice in invoices:
                daily_data[invoice.id] = serialize_invoice_data(invoice)
            
            filename = f"{current_date.strftime('%Y-%m-%d')}.json"
            filepath = output_path / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(daily_data, f, indent=2, ensure_ascii=False)
            
            files_created += 1
            total_invoices += len(invoices)
            print(f"  ✓ {filename}: {len(invoices)} invoices")
        else:
            print(f"  - {current_date.strftime('%Y-%m-%d')}: No invoices")
        
        current_date += timedelta(days=1)
    
    print(f"\n✅ Generated {files_created} JSON files with {total_invoices} total invoices")
    print(f"📁 Output directory: {output_path.absolute()}")
    
    return {
        "files_created": files_created,
        "total_invoices": total_invoices,
        "output_directory": str(output_path.absolute()),
        "date_range": {
            "first": first_date.strftime("%Y-%m-%d"),
            "last": last_date.strftime("%Y-%m-%d"),
        }
    }


async def main() -> None:
    load_dotenv()
    service = PrismaCrudService()
    await service.connect()

    try:
        stats = await generate_daily_invoice_json(service)
        return stats
    finally:
        await service.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
