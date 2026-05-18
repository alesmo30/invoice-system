# Invoice System - Apple Store Analytics

Sistema de gestión de facturas para retail tipo Apple Store: datos transaccionales en Supabase/Prisma, **RAG** sobre documentación manual (`seed/manual/`) con ChromaDB, y **agentes** LangGraph para atención (incluye flujo HITL y cotizaciones PDF).

## Tech Stack

- **Backend**: Python 3.13+
- **Database**: Supabase (PostgreSQL)
- **ORM**: Prisma Client Python
- **Vector store**: ChromaDB (colección local bajo `chroma_db_pipeline_completo/`)
- **Embeddings / retrieval**: `sentence-transformers`, BM25 opcional (`rank-bm25`)
- **Orquestación LLM**: LangChain / LangGraph
- **Proveedores LLM**: Google Gemini (`google-genai`) y Groq (`langchain_groq`, `groq`)
- **Evaluación RAG**: [Ragas](https://github.com/explodinggradients/ragas) + pruebas `pytest` de similitud semántica frente a casos golden
- **PDFs de cotización**: `fpdf2` (`pdf/cotization_generator.py`)
- **UI opcional**: Streamlit (`streamlit`)

---

## Running Python Scripts: `python -m` vs `python file.py`

### Cuándo usar `python -m module.path`

Cuando el script **importa módulos del proyecto** (`crud`, `seed`, `rag`, `agents`, etc.):

```bash
source venv/bin/activate

# Seeds y datos
python -m seed.products.seed_products
python -m seed.load_seed
python -m seed.verify_products

# RAG (índice y consultas sobre documentos Markdown)
python -m rag.main_rag_pipeline_v2

# Ragas / golden dataset
python -m rag.generate_golden_ragas
python -m rag.run_ragas_eval

# Playground supervisor (CLI interactivo)
python -m agents.playground.supervisor
```

**Por qué funciona**: el proyecto raíz entra en `sys.path`; imports tipo `from crud.prisma_crud import …` resuelven correctamente.

### Cuándo usar `python path/to/script.py`

Scripts **standalone** que solo usan paquetes externos:

```bash
python connection/supabase_connection.py
python connection/prisma_connection_test.py
```

### Error típico

```bash
# ❌ Falla con ModuleNotFoundError: No module named 'crud'
python seed/products/seed_products.py
```

---

## Quick Start

### 1. Entorno

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` incluye entre otros: Gemini/Groq/OpenAI, ChromaDB, LangChain/LangGraph, Ragas (`ragas`), `rapidfuzz` (golden Ragas), `pytest`, drivers Supabase/Postgres.

### 2. Variables de entorno

Copiá `.env.example` a `.env` y completá valores reales:

| Variable | Uso |
|----------|-----|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `DIRECT_URL` | Supabase / Prisma |
| `GEMINI_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, … | RAG / agentes (Gemini) |
| `GROQ_API_KEY`, `GROQ_MODEL`, … | Groq como alternativa; **obligatorio** para generación golden Ragas / algunos tests |
| `RAG_FAITHFULNESS`, `RAG_CONTEXT_PRECISION` | Métricas Ragas opcionales en supervisor (consumen llamadas extra) |
| `RUN_RAG_GOLDEN` | `1` junto con `pytest` para tests golden de similitud (ver abajo) |
| `QUOTE_*`, `QUOTE_PDF_OUTPUT_DIR` | Datos empresa y carpeta de PDFs de cotización |

### 3. Prisma

```bash
prisma generate
```

### 4. Conexión

```bash
python connection/supabase_connection.py
python connection/prisma_connection_test.py
```

### 5. Seed

```bash
python -m seed.products.seed_products
python -m seed.verify_products
python -m seed.load_seed
```

---

## Project Structure

```
invoice-system/
├── agents/playground/     # Supervisor LangGraph, ReAct DB/cotización, CLI interactivo
├── connection/            # supabase_connection.py, prisma_connection_test.py
├── crud/                  # prisma_crud.py
├── pdf/                   # Generación cotizaciones PDF (fpdf2)
├── prisma/                # schema.prisma
├── rag/                   # Ingestión, embeddings, retrieval, pipelines v1/v2/completo, Ragas
│   └── fixtures/golden/   # JSONL golden (generate_golden_ragas)
├── seed/
│   ├── manual/           # Markdown fuente para el índice RAG por defecto
│   └── …                 # load_seed, productos, etc.
├── tests/                 # pytest (p. ej. similitud RAG vs golden)
├── chroma_db_pipeline_completo/   # Persistencia Chroma (local; no suele estar en git)
├── pdfs/                  # Salida de cotizaciones (configurable)
├── .env.example
├── pytest.ini
└── README.md
```

Para convenciones y comandos resumidos del día a día, véase también **`AGENTS.md`**.

---

## RAG Pipeline

El pipeline recomendado para uso programático y CLI es **`rag.main_rag_pipeline_v2`**:

- Índice en disco: directorio **`chroma_db_pipeline_completo/`**, colección `rag_pipeline_completo`.
- Documentos por defecto: **`seed/manual/`** (Markdown). Podés cambiar la ruta con `--docs-dir`.
- Función típica: `answer_rag_query(...)` después de cargar el índice (ver docstring del módulo).

```bash
# Desde la raíz del repo, con venv activado
python -m rag.main_rag_pipeline_v2
```

Existen otros entry points (`rag/main_rag.py`, `main_rag_hybrid_search.py`, `main_rag_pipeline_completo.py`) para variantes experimentales o legado.

---

## Agentes (playground)

Supervisor que enruta intenciones (consultas DB vs RAG vs cotización) con **interrupts HITL** para clasificación dudosa y revisión de cotización.

```bash
python -m agents.playground.supervisor
```

La interacción multilínea está en `agents/playground/interactive_chat.py`.

---

## Evaluación RAG (Ragas y pytest golden)

### Dataset golden (Ragas TestsetGenerator)

Requiere **`GROQ_API_KEY`** en `.env`. Ejemplos:

```bash
# Un JSONL por documento (~17 preguntas/archivo por defecto)
python -m rag.generate_golden_ragas \
  --per-document \
  --docs-dir seed/manual/ \
  --output-dir rag/fixtures/golden/ \
  --verbose

# Un solo JSONL para todo el corpus
python -m rag.generate_golden_ragas --num-samples 10 --output rag/fixtures/rag_golden.jsonl
```

Por defecto el contexto se orienta a español; podés usar `--no-spanish-context` si aplica.

### Ragas desde CLI (`run_ragas_eval`)

Faithfulness y precisión de contexto; opciones detalladas en el módulo (p. ej. `--doc-context-precision`). Ver **`AGENTS.md`**.

### Pytest: similitud semántica RAG vs golden

- Configuración: `pytest.ini` (`pythonpath = .`, marcador `rag_golden`).
- Activa ejecución real con **`RUN_RAG_GOLDEN=1`**, `.env` con **`GROQ_API_KEY`**, índice en **`chroma_db_pipeline_completo/`**, y ficheros **`rag/fixtures/golden/*.jsonl`**.
- Resumen textual acumulativo: **`rag/fixtures/reports/golden_similarity_pytest_summary.txt`** (timestamp por bloque). Sobrescribir todo: **`RAG_GOLDEN_SUMMARY_OVERWRITE=1`**. Cambiar path: **`RAG_GOLDEN_SUMMARY_TXT`**.
- Umbral opcional: **`RAG_GOLDEN_MIN_COSINE`** (ej. `0.72`).

```bash
RUN_RAG_GOLDEN=1 pytest tests/rag/test_golden_semantic_similarity.py -v
```

Si algo se salta (`skip`), ejecutá `pytest -rs` para ver el motivo.

---

## Comandos habituales

### Base de datos

```bash
prisma generate
prisma migrate dev --name nombre_migracion
prisma studio
```

### Seeds

```bash
python -m seed.products.seed_products
python -m seed.load_seed
python -m seed.verify_products
```

### Conexión

```bash
python connection/supabase_connection.py
python connection/prisma_connection_test.py
```

---

## Roadmap (objetivos iniciales y siguientes pasos)

- [x] Conexión Supabase y Prisma
- [x] Esquema (employees, customers, products, invoices, invoice_items) y CRUD
- [x] Seed de productos y dataset de muestra de facturas
- [x] RAG sobre documentación manual + ChromaDB persistente (`main_rag_pipeline_v2`)
- [x] Playground multi-agente (supervisor LangGraph / cotización PDF)
- [x] Golden dataset Ragas + tests pytest de similitud semántica (opcional, con flags)
- [ ] Generación extensa de datos sintéticos (p. ej. 30 días de transacciones)
- [ ] Pipeline dedicado extracción diaria → JSON → diarios narrativos (si sigue siendo el diseño objetivo)

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'crud'`

Ejecutá desde la raíz con módulo: `python -m seed.products.seed_products` (no abras el `.py` directamente bajo `seed/` si importa `crud`/`rag`/etc.).

### Aviso de `datasource.url` en Prisma 7 tooling

Advertencia habitual del linter; **`prisma-client-py`** espera `url` en `schema.prisma`. En tiempo de ejecución suele funcionar.

### `rapidfuzz is required for string distance` (golden Ragas)

```bash
pip install -r requirements.txt
```

### Tests golden en skip o sin resumen TXT

Revisá `RUN_RAG_GOLDEN=1`, `GROQ_API_KEY`, existencia del índice `chroma_db_pipeline_completo/` y fixtures `rag/fixtures/golden/*.jsonl`. Motivo exacto: `pytest -rs`.

### Conexión

```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('DIRECT_URL'))"
```

---

## License

MIT
