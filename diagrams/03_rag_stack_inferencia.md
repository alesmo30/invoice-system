# RAG stack — vista para contexto del supervisor (`rag.main_rag_pipeline_v2`)

Diagrama corto útil antes de entrar en el grafo LangGraph.

```mermaid
flowchart LR
  subgraph fuentes["Fuente documentos"]
    MD[(Markdown<br/>seed/manual/ por defecto)]
  end

  subgraph build["Construcción índice (cuando se reindexa)"]
    L[load_directory]
    C[chunk_by_paragraphs]
    IDX[index_chunks<br/>colección rag_pipeline_completo]
    VS[(Chroma persistido<br/>chroma_db_pipeline_completo)]
    MD --> L --> C --> IDX --> VS
  end

  subgraph query["Consulta answer_rag_query"]
    Q[pregunta usuario]
    VS --> RET[advanced_rag_query<br/>retrieval híbrido / BM25 etc. según código]
    Q --> RET
    RET --> SYN[síntesis LLM opcional /<br/>compresión desactivada en tests golden]
    SYN --> OUT[texto respuesta<br/>± scores Ragas opcionales]
  end

  SUP[rag_agent supervisor] -.->|"import dinámico"| query
```

**Mensaje clave:** El supervisor no reimplementa RAG — delega en `answer_rag_query`; el mismo pipeline se **reaprovecha** en golden pytest para medir respuestas coherentes con el conocimiento indexado.
