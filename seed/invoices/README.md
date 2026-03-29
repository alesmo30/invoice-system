# Invoice Seeds

This directory contains scripts for seeding and exporting invoice data.

## Files

### `seed_invoices_30_days.py`
Generates 30 days of invoice data (March 1-30, 2026) with 8-10 invoices per day.

**Usage:**
```bash
source venv/bin/activate
PYTHONPATH=/Users/alejandro/Documents/AI-ENG-COD-FACILITO/invoice-system python seed/invoices/seed_invoices_30_days.py
```

### `generate_daily_json.py`
Exports all invoices from the database as daily JSON files. Each file contains all invoices for that specific date.

**Usage:**
```bash
source venv/bin/activate
PYTHONPATH=/Users/alejandro/Documents/AI-ENG-COD-FACILITO/invoice-system python seed/invoices/generate_daily_json.py
```

**Output:**
- Creates JSON files in `seed/invoices/daily_data/`
- File naming: `YYYY-MM-DD.json` (e.g., `2026-03-20.json`)
- Each file contains a JSON object where:
  - First-level keys are invoice IDs
  - Values are complete invoice objects with all related data

**JSON Structure:**
```json
{
  "invoice-uuid-1": {
    "invoice_number": "INV-2026-00172",
    "invoice_date": "2026-03-20",
    "total_amount": "1098",
    "created_at": "2026-03-24T07:19:38.730000+00:00",
    "employee": {
      "id": "...",
      "first_name": "...",
      "last_name": "...",
      "email": "...",
      "created_at": "..."
    },
    "customer": {
      "id": "...",
      "first_name": "...",
      "last_name": "...",
      "email": "...",
      "phone": "...",
      "created_at": "..."
    },
    "items": [
      {
        "id": "...",
        "quantity": 2,
        "unit_price": "549",
        "line_total": "1098",
        "created_at": "...",
        "product": {
          "id": "...",
          "name": "AirPods Max 2",
          "category": "Accessories",
          "sku": "AIRPODS-MAX-2",
          "unit_price": "549",
          "created_at": "..."
        }
      }
    ]
  },
  "invoice-uuid-2": { ... }
}
```

## Functions Added to `prisma_crud.py`

### `get_invoice_date_range()`
Returns the first and last invoice dates from the database.

**Returns:** `tuple[date | None, date | None]`

### `get_invoices_by_date(target_date: date)`
Fetches all invoices for a specific date with complete details including:
- Employee information
- Customer information
- Invoice items with product details

**Parameters:**
- `target_date`: The date to fetch invoices for

**Returns:** `list` of invoice objects with all related data
