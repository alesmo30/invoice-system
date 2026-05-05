# fpdf2 - Generador de PDF para Cotizaciones

## Instalación

```bash
pip install fpdf2
```

## Uso Básico

```python
from pdf.cotization_generator import parse_markdown_invoice, generate_invoice_pdf

md_text = """
## Cotización

- **Solicitante:** Juan Pérez
- **Vendedor:** María Gómez
- **Fecha:** 2024-09-16
- **Moneda:** USD

| Producto | SKU | Cant. | P. unit. (USD) | Subtotal (USD) |
|----------|-----|------:|---------------:|---------------:|
| iPhone 17 256GB | IPHONE-17-256 | 3 | 829.00 | 2,487.00 |
| AirPods Pro 3 | AIRPODS-PRO-3 | 1 | 249.00 | 249.00 |

- **Subtotal (USD):** 2,736.00
- **Total (USD):** 2,736.00

**Notas:** Descripción adicional aquí.

---
*Precios según catálogo consultado (USD).*
"""

data = parse_markdown_invoice(md_text)
data["invoice_number"] = "2024-0001"
data["currency"] = "USD"

generate_invoice_pdf(data, "cotizacion.pdf", logo_path="logo.png")
```

## Formato del Markdown

### Encabezado

```markdown
## Cotización
```

### Metadatos (requeridos)

```markdown
- **Solicitante:** Alejandro Estrada
- **Vendedor:** Camila Ruiz
- **Fecha:** 2024-09-16
- **Moneda:** USD
```

### Tabla de productos

| Columna | Descripción |
|--------|--------------|
| Producto | Nombre del producto |
| SKU | Código SKU |
| Cant. | Cantidad (entero) |
| P. unit. (USD) | Precio unitario |
| Subtotal (USD) | Cantidad × Precio unitario |

**Nota:** Usar separador `|------|` para indicar столбцы numéricos.

### Totales

```markdown
- **Subtotal (USD):** 2,736.00
- **Total (USD):** 2,736.00
```

### Notas (opcional)

```markdown
**Notas:** Descripción adicional del cliente o特殊情况.
```

### Footer (opcional)

```markdown
---
*Precios según catálogo consultado (USD).*
```

## Estructura del Dict Generado

```python
{
    "metadata": {
        "title": "Cotización",
        "solicitante": "Alejandro Estrada",
        "vendedor": "Camila Ruiz",
        "fecha": "2024-09-16",
        "moneda": "USD"
    },
    "items": [
        {
            "product": "iPhone 17 256GB",
            "sku": "IPHONE-17-256",
            "quantity": 3,
            "unit_price": Decimal("829.00"),
            "subtotal": Decimal("2487.00")
        }
    ],
    "subtotal": Decimal("2736.00"),
    "total": Decimal("2736.00"),
    "notes": "El cliente solicitó...",
    "footer": "Precios según catálogo consultado (USD)."
}
```

## Personalización

### Colores (InvoicePDF class)

```python
class InvoicePDF(FPDF):
    PRIMARY_COLOR = (0, 51, 102)   # Azul header
    ACCENT_COLOR = (240, 245, 250)  # Gris claro fondo
    TEXT_COLOR = (40, 40, 40)    # Negro texto
    MUTED_COLOR = (120, 120, 120) # Gris pie
```

### Logo

```python
generate_invoice_pdf(data, "factura.pdf", logo_path="logo.png")
```

Posición: esquina superior izquierda (15, 8), ancho 25mm.

## Ejecutar

```bash
python -m pdf.cotization_generator
```

Salida: `cotizacion.pdf`