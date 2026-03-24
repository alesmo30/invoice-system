# Invoice System - Apple Store Analytics

AI-powered invoice management system for Apple retail that transforms transactional data into structured JSON and natural language journals for RAG-based querying.

## Tech Stack

- **Backend**: Python 3.13+
- **Database**: Supabase (PostgreSQL)
- **ORM**: Prisma Client Python
- **Vector Store**: ChromaDB (local)
- **LLM Orchestration**: LangChain/LangGraph

---

## Running Python Scripts: `python -m` vs `python file.py`

### When to use `python -m module.path`

Use this when your script **imports from other project modules** (like `crud`, `seed`, etc.):

```bash
# ✅ CORRECT - Run as module from project root
source venv/bin/activate
python -m seed.products.seed_products
python -m seed.load_seed
python -m seed.verify_products
```

**Why it works:**
- Python treats the project root as the base for imports
- All project modules (`crud/`, `seed/`, etc.) become importable
- Imports like `from crud.prisma_crud import ...` resolve correctly

### When to use `python file.py`

Use this for **standalone scripts** that don't import from project modules:

```bash
# ✅ CORRECT - Standalone connection test
python prisma_connection_test.py
python connection/supabase_connection.py
```

**Why it works:**
- These scripts only import external packages (like `prisma`, `supabase`, `dotenv`)
- They don't depend on other project modules
- Direct file execution is simpler

### What happens if you use the wrong method?

```bash
# ❌ WRONG - Will fail with ModuleNotFoundError
python seed/products/seed_products.py

# Error: ModuleNotFoundError: No module named 'crud'
```

**Why it fails:**
- Python doesn't add the project root to `sys.path`
- Import `from crud.prisma_crud` can't find the `crud/` directory
- The script looks for modules relative to its own location, not the project root

---

## Quick Start

### 1. Environment Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install prisma python-dotenv supabase
```

### 2. Configure Environment Variables

Create `.env` in project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
DIRECT_URL=postgresql://postgres.xxx:[password]@aws-1-us-east-1.pooler.supabase.com:5432/postgres
```

### 3. Generate Prisma Client

```bash
prisma generate
```

### 4. Test Database Connection

```bash
# Test Supabase connection
python connection/supabase_connection.py

# Test Prisma connection
python prisma_connection_test.py
```

### 5. Seed Database

```bash
# Load product inventory (15 Apple products)
python -m seed.products.seed_products

# Verify products loaded
python -m seed.verify_products

# Load sample invoices
python -m seed.load_seed
```

---

## Project Structure

```
invoice-system/
├── connection/           # Database connection utilities
│   └── supabase_connection.py
├── crud/                 # Prisma CRUD operations
│   ├── __init__.py
│   └── prisma_crud.py
├── seed/                 # Database seeders
│   ├── __init__.py
│   ├── load_seed.py
│   ├── verify_products.py
│   └── products/
│       └── seed_products.py
├── prisma/
│   └── schema.prisma     # Database schema
├── .env                  # Environment variables (not in git)
└── README.md
```

---

## Common Commands

### Database Operations

```bash
# Generate Prisma client after schema changes
prisma generate

# Create migration
prisma migrate dev --name migration_name

# View database in Prisma Studio
prisma studio
```

### Seeding

```bash
# Seed products only
python -m seed.products.seed_products

# Seed full dataset (employees, customers, products, invoices)
python -m seed.load_seed

# Verify data
python -m seed.verify_products
```

### Connection Testing

```bash
# Test Supabase REST API connection
python connection/supabase_connection.py

# Test Prisma database connection
python prisma_connection_test.py
```

---

## Phase 0 Goals

- [x] Set up Supabase connection
- [x] Configure Prisma ORM
- [x] Define database schema (employees, customers, products, invoices, invoice_items)
- [x] Create CRUD service layer
- [x] Seed 15 Apple products
- [ ] Generate 30 days of synthetic transaction data
- [ ] Extract daily transactions to JSON
- [ ] Generate natural language journals from JSON
- [ ] Set up ChromaDB and ingest journals

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'crud'`

**Solution**: Run as module from project root:
```bash
python -m seed.products.seed_products  # ✅
# NOT: python seed/products/seed_products.py  # ❌
```

### Prisma schema validation warning

If you see a warning about `datasource.url` in Prisma 7:
- This is a **linter warning only** from Prisma 7 tooling
- Your project uses `prisma-client-py` (CLI 5.17) which **requires** `url` in schema
- The warning can be ignored — runtime works correctly

### Connection issues

Verify your `.env` variables:
```bash
# Check environment loads correctly
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('DIRECT_URL'))"
```

---

## License

MIT
