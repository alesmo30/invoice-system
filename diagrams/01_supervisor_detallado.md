# Supervisor LangGraph — flujo detallado (`agents/playground/supervisor.py`)

Vista ejecutiva para exposición: enrutamiento, **human-in-the-loop (HITL)** y responsabilidades de cada nodo.

> **Umbral clasificación:** el verificador usa `confidence >= 0.99` para aceptar automáticamente; si falla → `interrupt` y corrección por categoría + texto (`interactive_chat.py`).

## 1. Grafo principal (nodos y prioridad de enrutamiento)

```mermaid
flowchart TB
  START((START)) --> S[supervisor]
  S -->|"Clasificación JSON<br/>solo un campo texto"| A["assess_categorization<br/>Groq verificador GROQ_MODEL_CHECK"]

  A -->|"confianza menor que 0,99"| HITL_C{{interrupt classification_review}}
  HITL_C -->|"resume: categoría humana<br/>extracted_question"| A

  A -->|"confianza OK o tras HITL"| R{"route_after_supervisor<br/>prioridad fija"}

  R -->|1 cotización| QD[quote_draft_agent]
  R -->|2 RAG| RG[rag_agent]
  R -->|3 BD| DB[db_agent]
  R -->|4 saludo| GR[greeting_agent]
  R -->|sin categoría| END1((END))

  RG --> END_R((END))
  DB --> END_D((END))
  GR --> END_G((END))

  style HITL_C fill:#f9f,stroke:#333
```

**Aclaración:** `supervisor` y el **verificador** usan Groq (`GROQ_API_KEY`). Tras `interrupt`, LangGraph **reanuda** el mismo nodo `assess_categorization`, que fusiona la decisión humana y ejecuta la función `route_after_supervisor`.

**Prioridad codificada** (solo un camino simultáneo): cotización → RAG → base de datos → saludo → fin.

## 2. Ciclo cotización — borrador → revisión → PDF opcional

```mermaid
flowchart TB
  QD["quote_draft_agent<br/>(dentro: run_quote_react_agent<br/>Thought / Action / Observation)"] --> RQD{_route_after_quote_draft<br/>hay cotizacion_response?}

  RQD -->|sí: error recuperado<br/>con texto cliente| END1((END))

  RQD -->|no: cotizacion_draft listo| QR[quote_review_agent]

  QR --> MAX{¿ronda mayor o igual 12?<br/>QUOTE_REVIEW_MAX_ROUNDS}
  MAX -->|sí| END_AUTO[cotizacion_response = draft + aviso máximo<br/>sin más HITL]
  MAX -->|no| HITL_Q{{interrupt<br/>quote_review}}

  HITL_Q --> DEC{decisión vendedor}
  DEC -->|approved: true| PDF[write_pdf_on_quote_approval<br/>fpdf2 → pdfs/]
  PDF --> END2((END))
  DEC -->|replacement_markdown<br/>nuevo borrador| QR
  DEC -->|feedback texto| REGEN[cotización_react_input<br/>pregunta aumentada]
  REGEN --> QD

  style HITL_Q fill:#f9f,stroke:#333
  style DEC fill:#eef,stroke:#333
```

## 3. Qué hace cada worker (referencia rápida)

```mermaid
flowchart LR
  subgraph rag_worker["rag_agent"]
    AR1["answer_rag_query<br/>main_rag_pipeline_v2"]
    AR2{"¿RAG_FAITHFULNESS o<br/>RAG_CONTEXT_PRECISION en .env?"}
    AR3["métricas Ragas opcionales<br/>en estado del grafo"]
    AR4["fallback Groq si falla índice"]
    AR1 --> AR2
    AR2 -->|sí| AR3 --> OUT1["rag_query_response<br/>+ Ragas opcionales"]
    AR2 -->|no| OUT1
    AR1 -.->|"excepción pipeline"| AR4 --> OUT1
  end

  subgraph db_agent["db_agent"]
    DB1["run_db_react_agent<br/>max_steps 20"]
    DB2["Tools: schema + SELECT"]
    DB3["Groq fallback si BD falla"]
    DB1 --- DB2
    DB1 --> OUT2[db_query_response]
  end

  subgraph greeting_agent["greeting_agent"]
    G1["Sólo Groq LLM:<br/>jerga medellín, sin negocio"]
    G1 --> OUT3[greeting_response]
  end

  subgraph quote_draft_agent["quote_draft_agent (+ review)"]
    Q1["ReAct cotización"]
    Q2["Precios sólo BD products USD"]
    Q3["HITL vendedor + PDF"]
    Q1 --- Q2
    Q1 --> Q3
    Q3 --> OUT4[cotizacion_response + pdf path]
  end
```

### Tabla texto (speaker notes)

| Nodo | Entrada efectiva | Comportamiento clave |
|------|-------------------|---------------------|
| **supervisor** | último mensaje usuario | Una categoría: `cotización` > `BD` > `RAG` > `saludo` |
| **assess_categorization** | misma clase + texto completo copiado al campo ganador | Segundo modelo valida confianza; si baja → HITL |
| **rag_agent** | `rag_query_question` | Chroma + retrieval; Ragas sólo si flags env |
| **db_agent** | `db_query_question` | ReAct SQL lectura sólo sobre Postgres |
| **quote_draft_agent** | pregunta o `cotizacion_react_input` (feedback) | ReAct hasta Markdown de cotización |
| **quote_review_agent** | borrador Markdown | Interrupt; aprobación → PDF opcional |
