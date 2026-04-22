"""
main_rag_pipeline_completo.py — Pipeline RAG avanzado integrado

Pasos 1–3 (opcionales al iniciar): carga → chunking por párrafos → embeddings en ChromaDB
Paso 4: multi-query → hybrid → rerank → generar (por defecto sin compresión LLM intermedia)

Mismo patrón de ejecución que ``main_rag_hybrid_search``:
  - Al arrancar eliges si reejecutar ingest/indexación o usar ``./chroma_db_pipeline_completo``
  - Luego escribes preguntas en bucle (``salir`` para terminar)

Ejecutar:  python3 -m rag.main_rag_pipeline_completo
"""

from __future__ import annotations

import argparse
import os
import shutil
import time

from dotenv import load_dotenv

from rag.ingestion import load_directory, chunk_by_paragraphs
from rag.retrieval import advanced_rag_query
from rag.vectorstore import create_vectorstore, index_chunks, load_chunks_from_collection

load_dotenv()

BOLD = "\033[1m"
RESET = "\033[0m"
CYAN = "\033[96m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
DIM = "\033[2m"

CHROMA_DIR = "./chroma_db_pipeline_completo"
COLLECTION_NAME = "rag_pipeline_completo"


def header(paso: str, titulo: str, color: str = CYAN) -> None:
    print(f"\n{color}{BOLD}{'=' * 80}")
    print(f"  {paso}: {titulo}")
    print(f"{'=' * 80}{RESET}")


def _preguntar_reindexar() -> bool:
    """True = ejecutar pasos 1–3; False = usar Chroma existente en disco."""
    while True:
        raw = input(
            f"  {WHITE}{BOLD}¿Ejecutar pasos 1–3 "
            f"(carga, chunking e indexación)? [s/n]:{RESET} "
        ).strip().lower()
        if raw in ("s", "si", "sí", "y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print(f"  {YELLOW}Escribe s o n.{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG pipeline completo (multi-query + hybrid + rerank) sobre documentos locales."
    )
    parser.add_argument(
        "--docs-dir",
        default="seed/manual/",
        help="Carpeta con documentos (solo si reindexas pasos 1–3)",
    )
    parser.add_argument(
        "--con-compresion-llm",
        action="store_true",
        help=(
            "Antes de generar, comprime el contexto con un LLM "
            "(más llamadas al modelo; el modo por defecto lo omite)."
        ),
    )
    args = parser.parse_args()
    compress_with_llm: bool = args.con_compresion_llm

    print(f"\n{CYAN}{BOLD}{'=' * 80}")
    print("  RAG — Pipeline completo")
    print(f"{'=' * 80}{RESET}")
    flujo = (
        "multi-query → hybrid (BM25 + vector) → rerank → generar"
        if not compress_with_llm
        else "multi-query → hybrid → rerank → compresión LLM del contexto → generar"
    )
    modo = (
        f"{DIM}Modo:{RESET} ligero (sin compresión LLM intermedia)"
        if not compress_with_llm
        else f"{DIM}Modo:{RESET} con compresión LLM del contexto (--con-compresion-llm)"
    )
    print(f"""
  {modo}
  {DIM}Flujo: {flujo}
  Embeddings: paraphrase-multilingual-MiniLM-L12-v2 (local)
  Reranker:   cross-encoder/ms-marco-MiniLM-L-6-v2 (local)

  Al inicio: elige si reejecutar pasos 1–3 o usar el índice en {CHROMA_DIR}.{RESET}
""")

    if not os.environ.get("GROQ_API_KEY"):
        print(f"  {RED}{BOLD}ERROR: GROQ_API_KEY no configurada.{RESET}")
        print(f"  {DIM}export GROQ_API_KEY='gsk_...'{RESET}\n")
        return

    docs_dir = args.docs_dir
    if not docs_dir.endswith("/"):
        docs_dir = docs_dir + "/"

    ejecutar_pipeline = _preguntar_reindexar()
    all_chunks: list = []
    collection = None

    if ejecutar_pipeline:
        if not os.path.isdir(docs_dir):
            print(f"  {RED}No se encontró {docs_dir}{RESET}")
            return

        # =====================================================================
        # PASO 1: Carga de documentos
        # =====================================================================
        header("PASO 1", "Carga de documentos", GREEN)

        print(f"\n  Cargando desde: {BOLD}{docs_dir}{RESET}")
        t_load = time.time()
        documents = load_directory(docs_dir)
        load_time = time.time() - t_load

        print(f"\n  Documentos cargados: {BOLD}{len(documents)}{RESET} {DIM}({load_time:.2f}s){RESET}")
        for doc in documents:
            name = os.path.basename(doc.metadata["source"])
            words = len(doc.content.split())
            print(f"    - {name} ({words} palabras, {len(doc.content)} chars)")

        # =====================================================================
        # PASO 2: Chunking
        # =====================================================================
        header("PASO 2", "Chunking por párrafos (max 800 chars)", MAGENTA)

        for doc in documents:
            chunks = chunk_by_paragraphs(doc, max_chunk_size=800)
            all_chunks.extend(chunks)
            name = os.path.basename(doc.metadata["source"])
            print(f"    {MAGENTA}{name}: {BOLD}{len(chunks)} chunks{RESET}")

        print(f"\n  Total: {MAGENTA}{BOLD}{len(all_chunks)} chunks{RESET}")

        # =====================================================================
        # PASO 3: Indexación en ChromaDB
        # =====================================================================
        header("PASO 3", "Indexación en ChromaDB (embeddings locales)", CYAN)

        if os.path.exists(CHROMA_DIR):
            print("  Eliminando base de datos anterior...")
            shutil.rmtree(CHROMA_DIR)

        print(f"  Creando base en: {BOLD}{CHROMA_DIR}{RESET}")
        collection = create_vectorstore(COLLECTION_NAME, persist_dir=CHROMA_DIR)

        print("  Generando embeddings e indexando chunks...")
        t_idx = time.time()
        indexed = index_chunks(collection, all_chunks)
        idx_time = time.time() - t_idx
        print(f"\n  {CYAN}{BOLD}✓ {indexed} chunks indexados{RESET} {DIM}({idx_time:.2f}s){RESET}")
    else:
        header("Omitiendo pasos 1–3 (usar índice existente)", CYAN)
        if not os.path.isdir(CHROMA_DIR):
            print(
                f"  {RED}No existe {CHROMA_DIR}. Ejecuta de nuevo y responde s para indexar.{RESET}"
            )
            return
        print(f"  Abriendo colección en: {BOLD}{CHROMA_DIR}{RESET}")
        collection = create_vectorstore(COLLECTION_NAME, persist_dir=CHROMA_DIR)
        all_chunks = load_chunks_from_collection(collection)
        if not all_chunks:
            print(
                f"  {RED}La colección está vacía. Ejecuta con s para cargar e indexar.{RESET}"
            )
            return
        print(f"  {CYAN}{BOLD}✓ {len(all_chunks)} chunks cargados desde disco{RESET}")

    # =====================================================================
    # PASO 4: Pipeline completo (bucle de preguntas)
    # =====================================================================
    header("PASO 4", "Pipeline completo — integrado", CYAN)

    if compress_with_llm:
        orden = """
  {d}Orden interno:
    1. Multi-query   → reformulaciones de la pregunta
    2. Hybrid search → BM25 + vector por cada reformulación
    3. Re-ranking    → cross-encoder
    4. Compress      → oraciones relevantes (LLM extra)
    5. Generar       → respuesta final{d2}
""".format(d=DIM, d2=RESET)
    else:
        orden = """
  {d}Orden interno (ligero):
    1. Multi-query   → reformulaciones de la pregunta
    2. Hybrid search → BM25 + vector por cada reformulación (se fusionan candidatos)
    3. Re-ranking    → cross-encoder
    4. Generar       → respuesta usando el texto de los chunks rerankeados{d2}
""".format(d=DIM, d2=RESET)
    print(orden)

    print(f"\n  {GREEN}{BOLD}¡Listo para responder preguntas!{RESET}")
    print(f"  {DIM}(Escribe 'salir' para terminar){RESET}\n")

    while True:
        try:
            question = input(f"  {WHITE}{BOLD}Pregunta:{RESET} ").strip()

            if not question:
                continue

            if question.lower() in ("salir", "exit", "quit"):
                print(f"\n  {GREEN}¡Hasta luego!{RESET}\n")
                break

            print(f"\n  {DIM}Ejecutando pipeline de recuperación...{RESET}\n")

            t0 = time.time()
            answer = advanced_rag_query(
                collection,
                all_chunks,
                question,
                compress_with_llm=compress_with_llm,
            )
            elapsed = time.time() - t0

            print(f"\n  {GREEN}{BOLD}Respuesta:{RESET}")
            print(f"  {GREEN}{answer}{RESET}")
            print(f"  {DIM}(Pipeline en {elapsed:.2f}s){RESET}\n")
            print(f"  {'-' * 80}\n")

        except KeyboardInterrupt:
            print(f"\n\n  {GREEN}¡Hasta luego!{RESET}\n")
            break
        except Exception as e:
            print(f"\n  {RED}Error: {e}{RESET}\n")


if __name__ == "__main__":
    main()
