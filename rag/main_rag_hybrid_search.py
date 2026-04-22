"""
main_rag_hybrid_search.py — RAG con Hybrid Search

Script simplificado que implementa:
  1. Carga de documentos
  2. Chunking por empleado (1 chunk = 1 empleado)
  3. Indexación en ChromaDB
  4. Hybrid Search (BM25 + Vector Search)

Ejecutar:  python3 -m rag.main_rag_hybrid_search
"""

import os
import shutil
import time

from dotenv import load_dotenv
from openai import OpenAI

from rag.ingestion import load_directory, chunk_by_employee
from rag.retrieval import HybridRetriever
from rag.vectorstore import (
    create_vectorstore,
    index_chunks,
    load_chunks_from_collection,
)

load_dotenv()

# --- Colores ANSI ---
BOLD = "\033[1m"
RESET = "\033[0m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
DIM = "\033[2m"
WHITE = "\033[97m"

# --- Configuración del LLM (Groq) ---
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY"),
)
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

CHROMA_DIR = "./chroma_db_hybrid"


# =========================================================================
# Helpers
# =========================================================================

def header(titulo: str, color: str = CYAN) -> None:
    print(f"\n{color}{BOLD}{'=' * 80}")
    print(f"  {titulo}")
    print(f"{'=' * 80}{RESET}")


def info(texto: str) -> None:
    print(f"  {DIM}{texto}{RESET}")


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


def rag_generate(context: str, question: str) -> str:
    """Genera respuesta con el LLM usando contexto y pregunta."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Responde basándote ÚNICAMENTE en el contexto proporcionado. "
                    "Si no encuentras la respuesta, di 'No tengo información suficiente'. "
                    "Si la pregunta no tiene intencion de consultar sobre ventas, compras, inventario, etc. Di 'No tengo información suficiente'. "
                    "Nunca debes dar informacion que no este en el contexto proporcionado. "
                    "Nunca debes dar informacion sensible y no como estructuramos la informacion en el contexto. "
                    "Responde en español de forma clara y concisa."
                ),
            },
            {
                "role": "user",
                "content": f"CONTEXTO:\n{context}\n\nPREGUNTA: {question}",
            },
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content or ""


def print_results(results, color=YELLOW, max_preview=150) -> None:
    """Imprime los resultados de búsqueda."""
    for i, r in enumerate(results, 1):
        source = os.path.basename(r.metadata.get("source", "?"))
        preview = r.content[:max_preview].replace("\n", " ")
        if len(r.content) > max_preview:
            preview += "..."
        print(f"  {color}{i}. [{r.score:.4f}] [{source}]{RESET}")
        print(f"     {DIM}{preview}{RESET}")


# =========================================================================
# MAIN
# =========================================================================

def main() -> None:

    # Intro
    print(f"\n{CYAN}{BOLD}{'=' * 80}")
    print(f"   RAG con HYBRID SEARCH")
    print(f"{'=' * 80}{RESET}")
    print(f"""
  Pipeline simplificado de RAG con Hybrid Search:
  
    {GREEN}1. Carga de documentos{RESET}     — Lee archivos .txt del directorio
    {MAGENTA}2. Chunking por empleado{RESET}  — 1 chunk = 1 empleado (fecha + nombre + ventas)
    {CYAN}3. Indexación{RESET}             — Crea embeddings y almacena en ChromaDB
    {YELLOW}4. Hybrid Search{RESET}          — BM25 (keywords) + Vector (semántico)

  {DIM}LLM:        {MODEL} (Groq)
  Embeddings: paraphrase-multilingual-MiniLM-L12-v2 (local)
  Al inicio: elige si reejecutar pasos 1–3 o usar el índice en {CHROMA_DIR}.{RESET}
""")

    if not os.environ.get("GROQ_API_KEY"):
        print(f"  {RED}{BOLD}ERROR: GROQ_API_KEY no configurada.{RESET}")
        print(f"  {DIM}Configura: export GROQ_API_KEY='gsk_...'{RESET}\n")
        return

    ejecutar_pipeline = _preguntar_reindexar()
    all_chunks: list = []
    collection = None

    if ejecutar_pipeline:
        # =====================================================================
        # PASO 1: Carga de documentos
        # =====================================================================
        header("PASO 1: Carga de documentos", GREEN)

        docs_dir = "seed/invoices/daily-journal/"

        if not os.path.isdir(docs_dir):
            print(
                f"  {RED}No se encontró {docs_dir}. Asegúrate de tener los documentos.{RESET}"
            )
            return

        print(f"\n  Cargando documentos desde: {BOLD}{docs_dir}{RESET}")
        documents = load_directory(docs_dir)
        print(f"  Documentos cargados: {GREEN}{BOLD}{len(documents)}{RESET}")

        total_words = sum(len(doc.content.split()) for doc in documents)
        print(f"  Total de palabras: {DIM}{total_words:,}{RESET}")

        # =====================================================================
        # PASO 2: Chunking por empleado
        # =====================================================================
        header("PASO 2: Chunking por empleado", MAGENTA)

        print(f"\n  Estrategia: {BOLD}1 chunk = 1 empleado{RESET}")
        print(
            f"  Cada chunk contiene: fecha + nombre + UUID + todas sus transacciones\n"
        )

        for doc in documents:
            chunks = chunk_by_employee(doc)
            all_chunks.extend(chunks)
            name = os.path.basename(doc.metadata["source"])
            print(f"    {MAGENTA}{name}: {BOLD}{len(chunks)} chunks{RESET}")

        print(f"\n  {MAGENTA}{BOLD}Total: {len(all_chunks)} chunks{RESET}")

        # =====================================================================
        # PASO 3: Indexación en ChromaDB
        # =====================================================================
        header("PASO 3: Indexación en ChromaDB", CYAN)

        if os.path.exists(CHROMA_DIR):
            print(f"  Eliminando base de datos anterior...")
            shutil.rmtree(CHROMA_DIR)

        print(f"  Creando nueva base de datos en: {BOLD}{CHROMA_DIR}{RESET}")
        collection = create_vectorstore("rag_hybrid", persist_dir=CHROMA_DIR)

        print(f"  Generando embeddings e indexando chunks...")
        indexed = index_chunks(collection, all_chunks)
        print(f"\n  {CYAN}{BOLD}✓ {indexed} chunks indexados correctamente{RESET}")
    else:
        header("Omitiendo pasos 1–3 (usar índice existente)", CYAN)
        if not os.path.isdir(CHROMA_DIR):
            print(
                f"  {RED}No existe {CHROMA_DIR}. Ejecuta de nuevo y responde s para indexar.{RESET}"
            )
            return
        print(f"  Abriendo colección en: {BOLD}{CHROMA_DIR}{RESET}")
        collection = create_vectorstore("rag_hybrid", persist_dir=CHROMA_DIR)
        all_chunks = load_chunks_from_collection(collection)
        if not all_chunks:
            print(
                f"  {RED}La colección está vacía. Ejecuta con s para cargar e indexar.{RESET}"
            )
            return
        print(
            f"  {CYAN}{BOLD}✓ {len(all_chunks)} chunks cargados desde disco{RESET}"
        )

    # =====================================================================
    # PASO 4: Hybrid Search
    # =====================================================================
    header("PASO 4: Hybrid Search (BM25 + Vector)", YELLOW)

    print(f"""
  {BOLD}Hybrid Search{RESET} combina dos técnicas:
  
    • {YELLOW}BM25{RESET}         → Búsqueda por keywords exactas (fechas, nombres)
    • {CYAN}Vector Search{RESET} → Búsqueda semántica (significado)
    
  {DIM}Formula: score = alpha * vector_score + (1 - alpha) * bm25_score
  
  alpha = 0.5  → peso equilibrado (recomendado)
  alpha = 0.0  → solo BM25 (keywords)
  alpha = 1.0  → solo vector (semántico){RESET}
""")

    # Crear el retriever híbrido
    hybrid = HybridRetriever(collection, all_chunks, alpha=0.5)

    # Loop interactivo de preguntas
    print(f"\n  {GREEN}{BOLD}¡Listo para responder preguntas!{RESET}")
    print(f"  {DIM}(Escribe 'salir' para terminar){RESET}\n")

    while True:
        try:
            question = input(f"  {WHITE}{BOLD}Pregunta:{RESET} ").strip()

            if not question:
                continue

            if question.lower() in ["salir", "exit", "quit"]:
                print(f"\n  {GREEN}¡Hasta luego!{RESET}\n")
                break

            print(f"\n  {DIM}Buscando con Hybrid Search...{RESET}\n")

            # Búsqueda híbrida
            t0 = time.time()
            results = hybrid.search(question, top_k=5)
            search_time = time.time() - t0

            # Mostrar resultados
            print(f"  {YELLOW}{BOLD}Chunks recuperados (en {search_time:.2f}s):{RESET}\n")
            print_results(results, YELLOW)

            # Generar respuesta
            context = "\n\n---\n\n".join(r.content for r in results)

            print(f"\n  {DIM}Generando respuesta con LLM...{RESET}\n")
            t0 = time.time()
            answer = rag_generate(context, question)
            llm_time = time.time() - t0

            print(f"  {GREEN}{BOLD}Respuesta:{RESET}")
            print(f"  {GREEN}{answer}{RESET}")
            print(f"  {DIM}(Generada en {llm_time:.2f}s){RESET}\n")
            print(f"  {'-' * 80}\n")

        except KeyboardInterrupt:
            print(f"\n\n  {GREEN}¡Hasta luego!{RESET}\n")
            break
        except Exception as e:
            print(f"\n  {RED}Error: {e}{RESET}\n")


if __name__ == "__main__":
    main()
