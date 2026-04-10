# Annotated Journal Example

## Visual Breakdown of Document Structure

This document shows a real example from the dataset with annotations explaining each component.

---

## Full Document: 2026-03-04.txt

**NOTE:** This document has been updated (2026-04-09) to include the date header before each employee section for improved RAG retrieval.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4 de marzo de 2026                                                          │ ← DATE HEADER
│                                                                              │   (Now part of employee chunk)
│ Diego Fernandez (a25e9d70-4594-47a4-b7e4-11f67992d812):                    │ ← EMPLOYEE HEADER
│                                                                              │   - Full name
│ Durante esta jornada laboral se registraron las siguientes ventas: 1        │   - UUID for DB linkage
│ tablets iPad por un valor total de $749, 1 dispositivos iPhone por un       │
│ valor total de $1.029. Los clientes atendidos durante el día fueron         │ ← CATEGORY SUMMARY
│ Mariana Torres y Emiliano Vargas. El desglose detallado de las              │   - Product categories
│ transacciones incluye: la venta de iPad Air M4 11-inch 256GB a Mariana      │   - Category subtotals
│ Torres por $749, la venta de iPhone 17 512GB a Emiliano Vargas por          │
│ $1.029. El monto total de ventas generadas por Diego Fernandez durante      │ ← CUSTOMER LIST
│ esta jornada fue de $1.778 a través de 2 transacciones comerciales.         │   - All customers served
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘ ← TRANSACTION DETAILS
  ↑                                                                              - Product → Customer → Price
  Chunk 1: Complete employee report (Diego Fernandez)                           
  Size: ~600 characters                                                        ← DAILY TOTAL
                                                                                 - Employee's total sales
                                                                                 - Transaction count

┌─────────────────────────────────────────────────────────────────────────────┐
│ Camila Ruiz (3294eceb-4ac0-475f-a3cb-f74041dafe2a):                         │ ← EMPLOYEE HEADER
│                                                                              │
│ Durante esta jornada laboral se registraron las siguientes ventas: 1        │
│ computadoras Mac por un valor total de $1.499, 2 dispositivos iPhone por    │ ← CATEGORY SUMMARY
│ un valor total de $2.798, 1 accesorios por un valor total de $249. Los      │   - 3 categories
│ clientes atendidos durante el día fueron Daniel Garcia y Renata Castro.     │   - Higher complexity
│ El desglose detallado de las transacciones incluye: la venta de MacBook     │
│ Air M5 15-inch 512GB a Daniel Garcia por $1.499, la venta de iPhone 17      │ ← CUSTOMER LIST
│ Pro Max 1TB a Daniel Garcia por $1.599, la venta de iPhone 17 Pro 256GB     │   - 2 customers
│ a Renata Castro por $1.199, la venta de AirPods Pro 3 a Renata Castro       │
│ por $249. El monto total de ventas generadas por Camila Ruiz durante        │ ← TRANSACTION DETAILS
│ esta jornada fue de $4.546 a través de 3 transacciones comerciales.         │   - 4 line items
│                                                                              │   - 3 invoices
└─────────────────────────────────────────────────────────────────────────────┘
  ↑                                                                            ← DAILY TOTAL
  Chunk 2: Complete employee report (Camila Ruiz)                               - $4,546 total
  Size: ~750 characters                                                          - 3 transactions

┌─────────────────────────────────────────────────────────────────────────────┐
│ Valeria Soto (ced24730-05cc-4b53-8a9d-70e9b6278388):                        │
│                                                                              │
│ Durante esta jornada laboral se registraron las siguientes ventas: 2        │
│ tablets iPad por un valor total de $1.098, 7 accesorios por un valor        │ ← CATEGORY SUMMARY
│ total de $2.043, 1 dispositivos iPhone por un valor total de $1.199. Los    │   - 3 categories
│ clientes atendidos durante el día fueron Thiago Mendoza, Daniel Garcia,     │   - 7 accessories (high qty)
│ Mateo Hernandez y Valentina Lopez. El desglose detallado de las             │
│ transacciones incluye: la venta de iPad 11-inch 128GB Wi-Fi a Thiago        │ ← CUSTOMER LIST
│ Mendoza por $349, la venta de 3 unidades de AirPods Pro 3 a Valentina       │   - 4 customers
│ Lopez por $747, la venta de 3 unidades de AirPods Pro (2nd Gen) a           │
│ Valentina Lopez por $747, la venta de iPhone 17 Pro 256GB a Mateo           │ ← TRANSACTION DETAILS
│ Hernandez por $1.199, la venta de iPad Air M4 11-inch 256GB a Daniel        │   - 6 line items
│ Garcia por $749, la venta de AirPods Max 2 a Daniel Garcia por $549. El     │   - Multiple units notation
│ monto total de ventas generadas por Valeria Soto durante esta jornada       │   - "3 unidades de..."
│ fue de $4.340 a través de 4 transacciones comerciales.                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
  ↑
  Chunk 3: Complete employee report (Valeria Soto)
  Size: ~900 characters (approaching chunk limit)

┌─────────────────────────────────────────────────────────────────────────────┐
│ Alejandro Morales (d6993c62-ff6b-4d50-bfb4-c91bcd15f972):                   │
│                                                                              │
│ Durante esta jornada laboral se registraron las siguientes ventas: 1        │ ← CATEGORY SUMMARY
│ computadoras Mac por un valor total de $599. El cliente atendido durante    │   - Single category
│ el día fue Sofia Martinez. El desglose detallado de las transacciones       │   - Minimal report
│ incluye: la venta de MacBook Neo 13-inch a Sofia Martinez por $599. El      │
│ monto total de ventas generadas por Alejandro Morales durante esta          │ ← CUSTOMER LIST (singular)
│ jornada fue de $599 a través de 1 transacciones comerciales.                │   - "El cliente" (not "Los")
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘ ← TRANSACTION DETAILS
  ↑                                                                              - Single transaction
  Chunk 4: Complete employee report (Alejandro Morales)
  Size: ~400 characters (small report)                                         ← DAILY TOTAL
                                                                                 - $599 (lowest in file)
```

---

## Chunk Breakdown Analysis

### Chunk 0: Date Header
```
Content: "4 de marzo de 2026"
Size: 20 characters
Purpose: Temporal context for all subsequent employee reports
```

### Chunk 1: Diego Fernandez
```
Employee: Diego Fernandez
Categories: iPad (1), iPhone (1)
Customers: 2 (Mariana Torres, Emiliano Vargas)
Transactions: 2
Total: $1,778
Size: ~600 chars
```

### Chunk 2: Camila Ruiz
```
Employee: Camila Ruiz
Categories: Mac (1), iPhone (2), Accessories (1)
Customers: 2 (Daniel Garcia, Renata Castro)
Transactions: 3 (4 line items)
Total: $4,546
Size: ~750 chars
Notable: Daniel Garcia bought 2 items (Mac + iPhone)
```

### Chunk 3: Valeria Soto
```
Employee: Valeria Soto
Categories: iPad (2), Accessories (7), iPhone (1)
Customers: 4 (Thiago, Daniel, Mateo, Valentina)
Transactions: 4 (6 line items)
Total: $4,340
Size: ~900 chars
Notable: Valentina Lopez bought 6 AirPods (3+3 units)
         Largest chunk in this file
```

### Chunk 4: Alejandro Morales
```
Employee: Alejandro Morales
Categories: Mac (1)
Customers: 1 (Sofia Martinez)
Transactions: 1
Total: $599
Size: ~400 chars
Notable: Smallest report - single transaction
```

---

## Query Examples with Expected Retrieval

### Query 1: "¿Qué vendió Camila Ruiz el 4 de marzo de 2026?"

**Expected Retrieved Chunks:**
- **Chunk 0** (date header) - Score: 0.85 (date match)
- **Chunk 2** (Camila's report) - Score: 0.95 (employee + date match)
- **Chunk 3** (Valeria's report) - Score: 0.45 (date match only)

**Ideal Response:**
```
El 4 de marzo de 2026, Camila Ruiz vendió:
- MacBook Air M5 15-inch 512GB a Daniel Garcia por $1,499
- iPhone 17 Pro Max 1TB a Daniel Garcia por $1,599
- iPhone 17 Pro 256GB a Renata Castro por $1,199
- AirPods Pro 3 a Renata Castro por $249

Total del día: $4,546 en 3 transacciones comerciales.
```

---

### Query 2: "¿Quién compró AirPods el 4 de marzo?"

**Expected Retrieved Chunks:**
- **Chunk 3** (Valeria's report) - Score: 0.92 (AirPods Pro 3 + AirPods Pro 2nd Gen + AirPods Max 2)
- **Chunk 2** (Camila's report) - Score: 0.88 (AirPods Pro 3)
- **Chunk 0** (date header) - Score: 0.75 (date match)

**Ideal Response:**
```
El 4 de marzo de 2026, los siguientes clientes compraron AirPods:

Atendidos por Camila Ruiz:
- Renata Castro: AirPods Pro 3 por $249

Atendidos por Valeria Soto:
- Valentina Lopez: 3 unidades de AirPods Pro 3 por $747
- Valentina Lopez: 3 unidades de AirPods Pro (2nd Gen) por $747
- Daniel Garcia: AirPods Max 2 por $549
```

---

### Query 3: "¿Cuánto vendió Alejandro Morales ese día?"

**Expected Retrieved Chunks:**
- **Chunk 4** (Alejandro's report) - Score: 0.95 (employee match)
- **Chunk 0** (date header) - Score: 0.70 (date context)
- **Chunk 1** (Diego's report) - Score: 0.30 (same file)

**Ideal Response:**
```
El 4 de marzo de 2026, Alejandro Morales generó ventas por un total de $599 
a través de 1 transacción comercial.

Desglose:
- MacBook Neo 13-inch a Sofia Martinez por $599
```

---

### Query 4: "¿Qué clientes atendió Valeria Soto?"

**Expected Retrieved Chunks:**
- **Chunk 3** (Valeria's report) - Score: 0.98 (employee + customer list)
- **Chunk 0** (date header) - Score: 0.65 (temporal context)
- **Chunk 2** (Camila's report) - Score: 0.25 (same file)

**Ideal Response:**
```
El 4 de marzo de 2026, Valeria Soto atendió a los siguientes clientes:
- Thiago Mendoza (iPad 11-inch 128GB Wi-Fi por $349)
- Valentina Lopez (6 unidades de AirPods por $1,494)
- Mateo Hernandez (iPhone 17 Pro 256GB por $1,199)
- Daniel Garcia (iPad Air M4 + AirPods Max 2 por $1,298)
```

---

## Insights for Retrieval Optimization

### High-Performing Queries
✅ Employee name + date → Excellent precision (single chunk)
✅ Product name + date → Good precision (2-3 chunks)
✅ Customer name → Good recall (finds all mentions across dates)

### Challenging Queries
⚠️ "¿Cuántos iPhones se vendieron en total?" → Requires aggregation across all 30 files
⚠️ "¿Quién vendió más?" → Requires comparing totals across employees and dates
⚠️ "¿Qué día se vendió más?" → Requires summing all employee totals per day

### Recommended Enhancements
1. **Add metadata extraction:**
   ```python
   metadata = {
       "date": "2026-03-04",
       "employee": "Camila Ruiz",
       "employee_id": "3294eceb-4ac0-475f-a3cb-f74041dafe2a",
       "categories": ["Mac", "iPhone", "Accessories"],
       "total_sales": 4546,
       "transaction_count": 3
   }
   ```

2. **Implement hybrid search:**
   - Semantic search for natural language queries
   - Metadata filtering for structured queries (date ranges, employee filters)
   - BM25 for exact product name matching

3. **Add query routing:**
   - Aggregation queries → SQL database (Supabase)
   - Specific transaction queries → Vector search (ChromaDB)
   - Hybrid queries → Both systems + merge results

---

## File Statistics

```
Total Lines: 48
Total Chunks: 5 (1 date header + 4 employee reports)
Employees: 4
Customers: 9 unique
Transactions: 10 invoices
Line Items: 13 products sold
Total Sales: $11,263
Average per Employee: $2,815.75
Largest Sale: Camila Ruiz ($4,546)
Smallest Sale: Alejandro Morales ($599)
```
