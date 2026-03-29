from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Iterable

from prisma import Prisma


@dataclass
class InvoiceItemInput:
    product_id: str
    quantity: int
    unit_price: Decimal


class PrismaCrudService:
    def __init__(self) -> None:
        self.db = Prisma()

    async def connect(self) -> None:
        await self.db.connect()

    async def disconnect(self) -> None:
        await self.db.disconnect()

    async def upsert_employee(self, *, first_name: str, last_name: str, email: str):
        return await self.db.employee.upsert(
            where={"email": email},
            data={
                "create": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                },
                "update": {
                    "first_name": first_name,
                    "last_name": last_name,
                },
            },
        )

    async def upsert_customer(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str | None = None,
        phone: str | None = None,
    ):
        if email:
            return await self.db.customer.upsert(
                where={"email": email},
                data={
                    "create": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "phone": phone,
                    },
                    "update": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "phone": phone,
                    },
                },
            )

        return await self.db.customer.create(
            data={
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
            }
        )

    async def upsert_product(
        self,
        *,
        name: str,
        category: str,
        sku: str,
        unit_price: Decimal,
    ):
        return await self.db.product.upsert(
            where={"sku": sku},
            data={
                "create": {
                    "name": name,
                    "category": category,
                    "sku": sku,
                    "unit_price": unit_price,
                },
                "update": {
                    "name": name,
                    "category": category,
                    "unit_price": unit_price,
                },
            },
        )

    async def create_invoice(
        self,
        *,
        invoice_number: str,
        employee_id: str,
        customer_id: str | None,
        invoice_date: date,
        items: Iterable[InvoiceItemInput],
    ):
        normalized_items = list(items)
        total_amount = sum((item.unit_price * Decimal(str(item.quantity)) for item in normalized_items), Decimal("0.00"))

        create_data = {
            "invoice_number": invoice_number,
            "invoice_date": datetime.combine(invoice_date, time.min, tzinfo=timezone.utc),
            "total_amount": total_amount,
            "employee_id": employee_id,
            "items": {
                "create": [
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "line_total": item.unit_price * Decimal(str(item.quantity)),
                    }
                    for item in normalized_items
                ]
            },
        }
        if customer_id:
            create_data["customer_id"] = customer_id

        return await self.db.invoice.create(data=create_data, include={"items": True})

    async def list_invoices(self):
        return await self.db.invoice.find_many(
            include={
                "employee": True,
                "customer": True,
                "items": {"include": {"product": True}},
            },
            order={"invoice_date": "desc"},
        )

    async def get_invoice_date_range(self) -> tuple[date | None, date | None]:
        """Get the first and last invoice dates from the database."""
        first_invoice = await self.db.invoice.find_first(
            order={"invoice_date": "asc"}
        )
        last_invoice = await self.db.invoice.find_first(
            order={"invoice_date": "desc"}
        )
        
        first_date = first_invoice.invoice_date.date() if first_invoice else None
        last_date = last_invoice.invoice_date.date() if last_invoice else None
        
        return first_date, last_date

    async def get_invoices_by_date(self, target_date: date) -> list:
        """Get all invoices for a specific date with full details."""
        target_datetime = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        
        invoices = await self.db.invoice.find_many(
            where={
                "invoice_date": target_datetime
            },
            include={
                "employee": True,
                "customer": True,
                "items": {
                    "include": {
                        "product": True
                    }
                }
            },
            order={"invoice_number": "asc"}
        )
        
        return invoices
