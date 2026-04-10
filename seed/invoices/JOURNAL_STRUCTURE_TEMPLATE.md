# Daily Journal Structure Template

## Document Organization for RAG Retrieval

This template describes the hierarchical structure of daily sales journals to help the retriever understand chunk organization and improve semantic search accuracy.

---

## File-Level Structure

### Naming Convention
```
YYYY-MM-DD.txt
```
**Examples:** `2026-03-01.txt`, `2026-03-15.txt`, `2026-03-26.txt`

### Document Scope
- **One file per day** (30 files total: March 1-30, 2026)
- **Multiple employee reports** per file (3-5 employees per day)
- **Average size:** 40-55 lines per file (~2,500-3,500 characters)

---

## Hierarchical Information Architecture

```
📄 Daily Journal File (2026-03-DD.txt)
│
├── 👤 EMPLOYEE REPORT 1
│   ├── 📅 Date Header (repeated for each employee)
│   ├── Employee Name + UUID
│   ├── Sales Summary (by category)
│   ├── Customer List
│   ├── Transaction Details
│   └── Daily Total
│
├── 👤 EMPLOYEE REPORT 2
│   ├── 📅 Date Header (repeated for each employee)
│   └── [Same structure]
│
├── 👤 EMPLOYEE REPORT 3
│   ├── 📅 Date Header (repeated for each employee)
│   └── [Same structure]
│
└── 👤 EMPLOYEE REPORT N
    ├── 📅 Date Header (repeated for each employee)
    └── [Same structure]
```

**IMPORTANT CHANGE (2026-04-09):** The date header is now repeated before EACH employee section to ensure every chunk contains temporal context. This improves RAG retrieval accuracy by making each chunk self-contained.

---

## Employee Report Block Template

Each employee report follows this **exact narrative structure**:

```
{DATE_HEADER}

{EMPLOYEE_NAME} ({UUID}):

Durante esta jornada laboral se registraron las siguientes ventas: {CATEGORY_SUMMARY}. 
Los clientes atendidos durante el día fueron {CUSTOMER_LIST}. 
El desglose detallado de las transacciones incluye: {TRANSACTION_LIST}. 
El monto total de ventas generadas por {EMPLOYEE_NAME} durante esta jornada fue de ${TOTAL} 
a través de {N} transacciones comerciales.
```

**Note:** The date header is now included at the start of each employee block to ensure temporal context is always present in every chunk.

### Block Components

#### 1. **Date Header** (NEW - Added 2026-04-09)
```
4 de marzo de 2026
```
- **Format:** `{Day} de {Month} de {Year}`
- **Purpose:** Temporal context for the employee report
- **Placement:** First line of each employee block
- **Separation:** Blank line after

#### 2. **Employee Header**
```
Alejandro Morales (d6993c62-ff6b-4d50-bfb4-c91bcd15f972):
```
- **Format:** `{First Name} {Last Name} ({UUID}):`
- **Purpose:** Unique identifier for employee attribution
- **Separation:** Blank line before and after

#### 3. **Category Summary**
```
Durante esta jornada laboral se registraron las siguientes ventas: 
2 dispositivos iPhone por un valor total de $2.628, 
2 tablets iPad por un valor total de $1.098, 
1 accesorios por un valor total de $549.
```
- **Categories:** 
  - `dispositivos iPhone`
  - `tablets iPad`
  - `computadoras Mac`
  - `accesorios`
- **Format:** `{quantity} {category} por un valor total de ${amount}`
- **Purpose:** High-level sales breakdown by product type

#### 4. **Customer List**
```
Los clientes atendidos durante el día fueron Lucia Rivera, Isabella Rodriguez, 
Camila Perez y Santiago Gonzalez.
```
- **Format:** Comma-separated list with "y" before last name
- **Singular:** "El cliente atendido durante el día fue {Name}."
- **Plural:** "Los clientes atendidos durante el día fueron {Name1}, {Name2} y {Name3}."
- **Purpose:** Quick customer lookup for employee-customer relationships

#### 5. **Transaction Details**
```
El desglose detallado de las transacciones incluye: 
la venta de iPhone 17 Pro Max 1TB a Lucia Rivera por $1.599, 
la venta de iPad 11-inch 128GB Wi-Fi a Santiago Gonzalez por $349, 
la venta de 2 unidades de AirPods Pro 3 a Isabella Rodriguez por $498.
```
- **Format:** `la venta de {product} a {customer} por ${price}`
- **Quantity > 1:** `la venta de {N} unidades de {product} a {customer} por ${total}`
- **Purpose:** Granular transaction-level details for specific product queries

#### 6. **Daily Total**
```
El monto total de ventas generadas por Alejandro Morales durante esta jornada 
fue de $4.275 a través de 4 transacciones comerciales.
```
- **Format:** Fixed structure with employee name, total amount, and transaction count
- **Purpose:** Employee performance metrics

---

## Product Categories & Examples

### 1. **Dispositivos iPhone**
- iPhone 17e 256GB ($599)
- iPhone 17 256GB ($829)
- iPhone 17 512GB ($1,029)
- iPhone 17 Pro 256GB ($1,199)
- iPhone 17 Pro Max 1TB ($1,599)

### 2. **Tablets iPad**
- iPad 11-inch 128GB Wi-Fi ($349)
- iPad Air M4 11-inch 256GB ($749)

### 3. **Computadoras Mac**
- MacBook Neo 13-inch ($599)
- MacBook Air M5 13-inch 512GB ($1,199)
- MacBook Air M5 15-inch 512GB ($1,499)

### 4. **Accesorios**
- AirPods Pro (2nd Gen) ($249)
- AirPods Pro 3 ($249)
- AirPods Max 2 ($549)

---

## Employee Pool (5 Total)

| Employee Name | UUID |
|---------------|------|
| Alejandro Morales | d6993c62-ff6b-4d50-bfb4-c91bcd15f972 |
| Diego Fernandez | a25e9d70-4594-47a4-b7e4-11f67992d812 |
| Valeria Soto | ced24730-05cc-4b53-8a9d-70e9b6278388 |
| Mateo Vargas | b98b05be-c33c-4066-9ca0-7f76170674a6 |
| Camila Ruiz | 3294eceb-4ac0-475f-a3cb-f74041dafe2a |

---

## Chunking Strategy for RAG

### Current Implementation
- **Method:** `chunk_by_paragraphs()` in `rag/ingestion.py`
- **Max Chunk Size:** 1,300 characters
- **Separator:** `\n\n` (double newline)
- **Preservation:** Never splits paragraphs mid-sentence

### Natural Chunk Boundaries

Given the structure, chunks will naturally break at:

1. **Date Header** (isolated chunk)
   ```
   1 de marzo de 2026
   ```

2. **Employee Report Blocks** (1-2 chunks per employee)
   - Small reports (1-3 transactions): Single chunk
   - Large reports (4+ transactions): May split into 2 chunks
   - **Ideal:** Each employee report = 1 complete chunk

### Chunk Metadata Structure

```python
Chunk(
    content="Alejandro Morales (d6993c62-ff6b-4d50-bfb4-c91bcd15f972):\n\nDurante esta jornada...",
    metadata={
        "source": "seed/invoices/daily-journal/2026-03-01.txt",
        "type": "txt",
        "chunk_index": 1
    },
    chunk_id="uuid-generated"
)
```

---

## Query Patterns & Retrieval Optimization

### Common Query Types

#### 1. **Employee-Specific Queries**
```
"¿Qué vendió Camila Ruiz el 4 de marzo de 2026?"
"¿Cuánto vendió Alejandro Morales el día 15?"
```
**Retrieval Target:** Employee report block for specific date
**Key Entities:** Employee name + date

#### 2. **Product-Specific Queries**
```
"¿Quién vendió el iPhone 17 Pro Max?"
"¿Cuántos AirPods Max 2 se vendieron?"
```
**Retrieval Target:** Transaction details section
**Key Entities:** Product name

#### 3. **Customer-Specific Queries**
```
"¿Qué compró Isabella Rodriguez?"
"¿Quién atendió a Nicolas Flores?"
```
**Retrieval Target:** Customer list + transaction details
**Key Entities:** Customer name

#### 4. **Date-Range Queries**
```
"¿Cuáles fueron las ventas totales del 1 al 5 de marzo?"
"¿Qué días vendió más Valeria Soto?"
```
**Retrieval Target:** Multiple date headers + employee totals
**Key Entities:** Date range + optional employee name

#### 5. **Category Queries**
```
"¿Cuántas computadoras Mac se vendieron?"
"¿Qué empleado vendió más iPads?"
```
**Retrieval Target:** Category summary sections
**Key Entities:** Product category

---

## Semantic Search Optimization Tips

### For Retriever Configuration

1. **Increase `n_results`** for queries spanning multiple days
   - Single-day queries: `n_results=3` (current)
   - Multi-day queries: `n_results=5-10`

2. **Embedding Model Considerations**
   - Current: Default sentence-transformers
   - Recommendation: Spanish-optimized model for better semantic understanding
   - Example: `paraphrase-multilingual-MiniLM-L12-v2`

3. **Metadata Filtering**
   - Add date extraction from filenames to metadata
   - Enable filtering by date range before semantic search
   ```python
   metadata={
       "source": "seed/invoices/daily-journal/2026-03-01.txt",
       "type": "txt",
       "chunk_index": 1,
       "date": "2026-03-01",  # ← Add this
       "employee": "Alejandro Morales"  # ← Extract from content
   }
   ```

### For LLM Prompt Engineering

Include this context in system prompts:

```
CONTEXTO DE ESTRUCTURA:
- Cada documento representa un día de ventas
- Cada bloque de párrafo corresponde a un empleado específico
- Los datos están organizados en: resumen por categoría → lista de clientes → detalles de transacciones → total diario
- Las fechas están en formato español: "D de mes de YYYY"
- Los montos están en dólares USD con formato $X,XXX
```

---

## Example: Full Employee Report

```
Mateo Vargas (b98b05be-c33c-4066-9ca0-7f76170674a6):

Durante esta jornada laboral se registraron las siguientes ventas: 3
computadoras Mac por un valor total de $4.197, 1 tablets iPad por un valor total
de $749, 6 accesorios por un valor total de $1.794. Los clientes atendidos
durante el día fueron Nicolas Flores, Mariana Torres, Isabella Rodriguez,
Valentina Lopez y Emiliano Vargas. El desglose detallado de las transacciones
incluye: la venta de MacBook Air M5 13-inch 512GB a Isabella Rodriguez por
$1.199, la venta de iPad Air M4 11-inch 256GB a Mariana Torres por $749, la
venta de AirPods Max 2 a Mariana Torres por $549, la venta de MacBook Air M5
15-inch 512GB a Emiliano Vargas por $1.499, la venta de AirPods Pro 3 a Nicolas
Flores por $249, la venta de 4 unidades de AirPods Pro (2nd Gen) a Nicolas
Flores por $996, la venta de MacBook Air M5 15-inch 512GB a Valentina Lopez por
$1.499. El monto total de ventas generadas por Mateo Vargas durante esta jornada
fue de $6.740 a través de 5 transacciones comerciales.
```

**Extracted Information:**
- **Employee:** Mateo Vargas (b98b05be-c33c-4066-9ca0-7f76170674a6)
- **Date:** 26 de marzo de 2026 (from file header)
- **Categories:** 3 Mac, 1 iPad, 6 accessories
- **Customers:** 5 unique (Nicolas, Mariana, Isabella, Valentina, Emiliano)
- **Transactions:** 7 line items across 5 invoices
- **Daily Total:** $6,740

---

## Version History

- **v1.0** (2026-04-09): Initial template based on 30-day March 2026 dataset
- **Dataset:** 30 files, ~1,403 lines total, 5 employees, 15 products

---

## Usage Notes

This template should be:
1. **Referenced** by the RAG system prompt for query understanding
2. **Used** to train/fine-tune retrieval models on structure
3. **Updated** if journal format changes in future phases
4. **Shared** with LLM for better context-aware response generation
