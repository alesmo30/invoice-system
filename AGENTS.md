# AGENTS.md - Invoice System

## Critical: Python Module Loading

```bash
# ✅ Scripts importing project modules (crud, seed, rag...)
python -m seed.products.seed_products
python -m seed.load_seed
python -m rag.main_rag_pipeline_v2
python -m rag.run_ragas_eval          # RAGAS: faithfulness + context precision (--doc-context-precision)
python -m rag.generate_golden_ragas   # Golden JSONL con Ragas TestsetGenerator (GROQ_API_KEY)

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

# RAG golden (Ragas): GROQ_API_KEY; español por defecto (omitir con --no-spanish-context).
# Por documento (recomendado, ~17 preguntas/archivo por defecto → rag/fixtures/golden/*.jsonl):
python -m rag.generate_golden_ragas --per-document --docs-dir seed/manual/ --output-dir rag/fixtures/golden/ --verbose
# Todo el corpus en un solo JSONL:
python -m rag.generate_golden_ragas --num-samples 10 --output rag/fixtures/rag_golden.jsonl

# pytest: RAG vs golden (similitud coseno embeddings locales; mismo modelo que rag/embeddings)
# Requiere RUN_RAG_GOLDEN=1, GROQ_API_KEY, índice en chroma_db_pipeline_completo/
# pytest: métricas por caso en consola si RUN_RAG_GOLDEN=1 (véase tests/rag/conftest.py)
# Reporte TXT acumulativo por timestamp en rag/fixtures/reports/golden_similarity_pytest_summary.txt
# Sobrescribe todo: RAG_GOLDEN_SUMMARY_OVERWRITE=1. Path: RAG_GOLDEN_SUMMARY_TXT=...
RUN_RAG_GOLDEN=1 pytest tests/rag/test_golden_semantic_similarity.py -v
# Opcional: --log-cli-level=INFO --log-cli-format="%(message)s" si prefieres el log estándar de pytest
# Umbral opcional: RAG_GOLDEN_MIN_COSINE=0.72

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
| `rapidfuzz is required for string distance` (golden) | `pip install -r requirements.txt` (incluye `rapidfuzz` para Ragas testset) |
| pytest golden TXT resumen / skips | Reporte TXT **acumulativo** (bloques por `timestamp_utc`) en `rag/fixtures/reports/golden_similarity_pytest_summary.txt`; sobrescribe todo con `RAG_GOLDEN_SUMMARY_OVERWRITE=1`. Override: `RAG_GOLDEN_SUMMARY_TXT`. Skips: `RUN_RAG_GOLDEN=1`, `.env` con `GROQ_API_KEY`, índice `chroma_db_pipeline_completo/`, `/rag/fixtures/golden/*.jsonl`. Motivo: `pytest -rs` |