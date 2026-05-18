# Diagramas (presentación — Invoice System)

Los `.md` de esta carpeta son la **fuente** (Markdown + diagramas en Mermaid). Durante una charla, **no conviene proyectar el código** del `.md`; la audiencia apenas entiende los bloques Mermaid sin renderizar.

## Qué formato usar para exponer bien

| Objetivo | Formato recomendado | Por qué |
|---------|---------------------|---------|
| **Diapositivas** (Google Slides, PowerPoint, Keynote, Obsidian Presentation) | **SVG** si el programa lo lleva bien; si no, **PNG 2×** (anchura grande, p.ej. 2400 px) | Se leen textos con zoom del proyector; una figura visible por lámina |
| **Imprimir / entregar dossier único** | **PDF** (varias páginas, cada una = un diagrama o una figura grande) | Un solo archivo; buena para comité o anexo |
| **Web / repos** | **Markdown en GitHub** o **HTML** renderizado | El Mermaid ya se dibuja; no es necesariamente cómodo como “slideshow” |

**PDF no es inherentemente “mejor” que PNG/SVG**: normalmente primero **exportás cada diagrama como imagen (SVG o PNG)** y después armás PDF o láminas. Si proyectás PDF página a página suele estar bien para textos densos; para diagramas igual querés tamaño grande y buen contraste.

### Cómo generar PNG o SVG rápido (sin instalar nada crítico)

1. Abrí el `.md`, copiá solo el contenido dentro del fence ` ```mermaid ` … ` ``` `.
2. Pegalo en **[Mermaid Live Editor](https://mermaid.live/)** (renderiza solo).
3. Menú **Actions → PNG** o **SVG** (PNG para máxima compatibilidad en diapositivas).

Repetí una exportación por diagrama si un archivo tiene varios bloques Mermaid — **convención de nombres** sugerida: `diagrams/export/01_supervisor_grafo_principal.svg`.

### Opcional por terminal ( reproducible )

Si tenés Node.js instalado podés automatizar ([Mermaid CLI](https://github.com/mermaid-js/mermaid-cli)):

```bash
# ejemplo: crear un archivo .mmd con el código copiado del .md y luego:
npx --yes @mermaid-js/mermaid-cli@latest -i diagrama.mmd -o diagramas/export/diagrama.svg
npx --yes @mermaid-js/mermaid-cli@latest -i diagrama.mmd -o diagramas/export/diagrama.png -w 2400 -H 1800 -b transparent
```

Carpeta sugerida para arte exportado (podés crearla vos): **`diagrams/export/`** (opcional `.gitignore` si no querés versionar PNG masivos).

### Consejos al armar láminas

- **Una idea grande por slides**: partir `01_supervisor_detallado` en 2–3 figuras ya ayuda más que todo en un lienzo diminuto.
- **Textos**: en export, si queda muy chico aumentá tamaño del diagrama en Mermaid (menos nodos por figura suele hacer más efecto que “zoom” digital).
- **Título en la lámina**, no dentro del PNG: el público enlaza rápido con lo que decis.

---

Los `.md` siguen sirviendo para **mantener los diagramas bajo control de código** y versionarlos; las imágenes son la capa de **presentación**.

| Archivo | Para qué sirve |
|---------|----------------|
| [**01_supervisor_detallado.md**](./01_supervisor_detallado.md) | Flujo LangGraph del supervisor: clasificación, HITL, RAG, DB ReAct, cotización + PDF |
| [**02_golden_pytest_similitud.md**](./02_golden_pytest_similitud.md) | Golden JSONL → pytest → embeddings → similitud coseno y reporte |
| [**03_rag_stack_inferencia.md**](./03_rag_stack_inferencia.md) | Vista compacta del RAG que consume el supervisor (Chroma + pipeline v2) |
| [**04_react_bd_cotizacion.md**](./04_react_bd_cotizacion.md) | Ciclo Thought–Action–Observation en agentes especializados |

**Sugerencia al exponer:** empezá por **03** (contexto técnico), **01** (corazón del producto), **02** (calidad/evidencias), **04** (detalle opcional si preguntan).

## Incluir en el PDF de documentación final

El script `pdf/generate_project_summary_pdf.py` renderiza automáticamente todos los bloques Mermaid de esta carpeta y los añade al final de `docs/Invoice_System_Resumen_Proyecto.pdf` (requiere **Node.js** + `npx`).

```bash
python pdf/generate_project_summary_pdf.py
python pdf/generate_project_summary_pdf.py --force-diagrams   # regenerar PNG en diagrams/export/pdf_build/
```

Los PNG intermedios quedan en `diagrams/export/pdf_build/`.
