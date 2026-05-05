# AGENTS.md - Invoice System

## Critical: Python Module Loading

```bash
# ✅ Scripts importing project modules (crud, seed, rag...)
python -m seed.products.seed_products
python -m seed.load_seed
python -m rag.main_rag_pipeline_v2

# ✅ Standalone scripts (external deps only)
python connection/supabase_connection.py
python prisma_connection_test.py

# ❌ WRONG - Will fail with ModuleNotFoundError
python seed/products/seed_products.py
```

**Why**: `python -m` adds project root to `sys.path`, enabling imports like `from crud.prisma_crud import ...`

---

## Required Setup

```bash
# 1. Environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure .env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=your_key
DIRECT_URL=postgresql://postgres.xxx@aws-1-us-east-1.pooler.supabase.com:5432/postgres

# 3. Generate Prisma client
prisma generate

# 4. Test connection
python connection/supabase_connection.py
python prisma_connection_test.py
```

---

## Key Commands

```bash
# Database
prisma generate           # After schema changes
prisma migrate dev --name init
prisma studio            # Visual DB editor

# Seeding
python -m seed.products.seed_products  # Products only
python -m seed.load_seed                # Full dataset
python -m seed.verify_products          # Verify data
```

---

## Project Structure

- `crud/prisma_crud.py` - Database operations
- `seed/` - Data seeding (products, invoices)
- `rag/` - RAG pipeline for query
- `agents-guide/` - Multi-agent systems
- `prisma/schema.prisma` - Database schema

---

## Database Schema (Supabase PostgreSQL)

- `employees` - Staff (id, first_name, last_name, email)
- `customers` - Buyers (id, first_name, last_name, email, phone)
- `products` - Apple products (id, name, category, sku, unit_price)
- `invoices` - Sales (id, invoice_number, employee_id, customer_id, total_amount)
- `invoice_items` - Line items (invoice_id, product_id, quantity, unit_price, line_total)

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'crud'` | Use `python -m seed.xxx`, not `python seed/xxx.py` |
| Prisma datasource warning | Ignore - linter warning only, runtime works |