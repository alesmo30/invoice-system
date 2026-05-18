# ReAct interno — BD y cotización (`db_react_agent` / `quote_react_agent`)

Para preguntas de audiencia técnica: cómo convergen herramientas y el LLM dentro de cada agente especializado.

## Agente BD (solo lectura)

```mermaid
sequenceDiagram
  participant U as Pregunta usuario
  participant M as Modelo Groq
  participant T as Herramientas Python
  participant DB as Postgres / Supabase

  U ->> M: System + mensaje (formato Thought/Action)
  loop hasta Finish o máximo pasos
    M ->> M: Thought N
    M ->> T: Action: get_database_schema o execute_readonly_query
    T ->> DB: SELECT validado sólo lectura
    DB -->> T: filas / error
    T -->> M: Observation N
  end
  M -->> U: Finish[respuesta natural en español]
```

## Agente cotización (catálogo + documento Markdown)

```mermaid
flowchart TB
  Q[Pregunta cliente] --> R[Ronda ReAct: schema / SELECT products]
  R -->|"precios sólo BD USD"| SUM[Resume líneas cantidad × unit_price]
  SUM --> PHASE2[Fase siguiente: JSON Pydantic validado<br/>Markdown estructura cotización]
  PHASE2 --> OUT[Borrador para quote_review_agent]

  subgraph tools["Comparte utilidades DB con db_react"]
    EX["execute_db_tool / parse_db_action"]
  end
  R --- tools
```

**Diferenciación rápida en charla:**

- **BD general:** cualquier tabla permitida por `db_tools` (consultas tienda/inventario/ventas).
- **Cotización:** playbook orientado a `products`; el borrador debe justificar totales antes del HITL del vendedor.
