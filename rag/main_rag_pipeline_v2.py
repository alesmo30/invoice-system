"""
main_rag_pipeline_v2.py — Misma lógica de índice y consulta que v1, con API programática.

- ``answer_rag_query(question)``: sin input(); carga Chroma en disco (o usa caché en memoria).
- CLI: misma pregunta inicial de reindex que v1, luego bucle de preguntas o ``--query``.

No modifica ``main_rag_pipeline_completo.py``. Rutas absolutas a la raíz del repo para no depender del cwd.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import logging
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from rag.ingestion import load_directory, chunk_by_paragraphs
from rag.retrieval import advanced_rag_query
from rag.vectorstore import create_vectorstore, index_chunks, load_chunks_from_collection

load_dotenv()

logger = logging.getLogger(__name__)

BOLD = "\033[1m"
RESET = "\033[0m"
CYAN = "\033[96m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
DIM = "\033[2m"

_REPO_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = str(_REPO_ROOT / "chroma_db_pipeline_completo")
COLLECTION_NAME = "rag_pipeline_completo"

_collection = None
_chunks: list = []


def _normalize_docs_dir(docs_dir: str) -> str:
    d = docs_dir.strip()
    d = d if d.endswith("/") else d + "/"
    if os.path.isabs(d):
        return d
    rel = d.lstrip("./")
    return str(_REPO_ROOT / rel)


def header(paso: str, titulo: str, color: str = CYAN) -> None:
    print(f"\n{color}{BOLD}{'=' * 80}")
    print(f"  {paso}: {titulo}")
    print(f"{'=' * 80}{RESET}")


def _preguntar_reindexar() -> bool:
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


def _build_index(docs_dir: str) -> tuple:
    global _collection, _chunks
    if not os.path.isdir(docs_dir):
        raise FileNotFoundError(f"No se encontró la carpeta de documentos: {docs_dir}")

    header("PASO 1", "Carga de documentos", GREEN)
    print(f"\n  Cargando desde: {BOLD}{docs_dir}{RESET}")
    t_load = time.time()
    documents = load_directory(docs_dir)
    print(
        f"\n  Documentos cargados: {BOLD}{len(documents)}{RESET} "
        f"{DIM}({time.time() - t_load:.2f}s){RESET}"
    )

    header("PASO 2", "Chunking por párrafos (max 800 chars)", MAGENTA)
    all_chunks: list = []
    for doc in documents:
        chunks = chunk_by_paragraphs(doc, max_chunk_size=800)
        all_chunks.extend(chunks)
        name = os.path.basename(doc.metadata["source"])
        print(f"    {MAGENTA}{name}: {BOLD}{len(chunks)} chunks{RESET}")
    print(f"\n  Total: {MAGENTA}{BOLD}{len(all_chunks)} chunks{RESET}")

    header("PASO 3", "Indexación en ChromaDB (embeddings locales)", CYAN)
    if os.path.exists(CHROMA_DIR):
        print("  Eliminando base de datos anterior...")
        shutil.rmtree(CHROMA_DIR)
    print(f"  Creando base en: {BOLD}{CHROMA_DIR}{RESET}")
    collection = create_vectorstore(COLLECTION_NAME, persist_dir=CHROMA_DIR)
    print("  Generando embeddings e indexando chunks...")
    t_idx = time.time()
    indexed = index_chunks(collection, all_chunks)
    print(
        f"\n  {CYAN}{BOLD}✓ {indexed} chunks indexados{RESET} "
        f"{DIM}({time.time() - t_idx:.2f}s){RESET}"
    )
    _collection = collection
    _chunks = all_chunks
    return collection, all_chunks


def _load_from_disk() -> tuple:
    global _collection, _chunks
    if not os.path.isdir(CHROMA_DIR):
        raise FileNotFoundError(
            f"No existe el índice en {CHROMA_DIR}. "
            "Ejecute este módulo en modo CLI y elija indexar (s), o use el pipeline v1 una vez."
        )
    collection = create_vectorstore(COLLECTION_NAME, persist_dir=CHROMA_DIR)
    chunks = load_chunks_from_collection(collection)
    if not chunks:
        raise ValueError(
            f"La colección en {CHROMA_DIR} está vacía. Vuelva a indexar (pasos 1–3)."
        )
    _collection = collection
    _chunks = chunks
    logger.info("RAG v2: cargados %d chunks desde disco", len(chunks))
    return collection, chunks


def ensure_rag_resources(*, reindex: bool = False, docs_dir: str = "seed/manual/") -> tuple:
    """
    Prepara colección y chunks. Con ``reindex=True`` reconstruye el índice desde ``docs_dir``.
    Sin reindex, usa caché en memoria si ya existe; si no, abre Chroma en disco.
    """
    global _collection, _chunks
    docs_dir = _normalize_docs_dir(docs_dir)
    if reindex:
        return _build_index(docs_dir)
    if _collection is not None and _chunks:
        return _collection, _chunks
    return _load_from_disk()


def clear_rag_cache() -> None:
    """Útil tras reindex externo; fuerza a recargar desde disco en la próxima consulta."""
    global _collection, _chunks
    _collection = None
    _chunks = []


def _run_rag_with_stdout_captured(
    collection,
    chunks,
    q: str,
    *,
    compress_with_llm: bool,
) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return advanced_rag_query(
            collection,
            chunks,
            q,
            compress_with_llm=compress_with_llm,
        )


def _spin_thinking_while(tty, future) -> None:
    """
    Animación en la consola real (sys.__stdout__) mientras el worker redirige su propio stdout.
    Spinner braille + puntos que ciclan, similar a indicadores de “procesando”.
    """
    spin = itertools.cycle("⣾⣽⣻⢿⡿⣟⣯⣷")
    msg = "Thinking"
    n = 0
    line = ""
    try:
        while not future.done():
            glyph = next(spin)
            dots = "." * (n % 4)
            n += 1
            line = f"{glyph} {msg}{dots}"
            tty.write(f"\r{line}   ")
            tty.flush()
            time.sleep(0.1)
    finally:
        clear_w = max(len(line) + 4, 36)
        tty.write("\r" + " " * clear_w + "\r")
        tty.flush()


def answer_rag_query(
    question: str,
    *,
    compress_with_llm: bool = False,
    show_thinking: bool | None = None,
) -> str:
    """
    Ejecuta el pipeline completo (multi-query → hybrid → rerank → generar) sobre ``question``.
    No hace input(); requiere índice existente o una indexación previa vía CLI.

    Con ``show_thinking=True`` (por defecto si stdout es TTY) muestra una animación “Thinking”
    mientras el pipeline corre en segundo plano.
    """
    q = (question or "").strip()
    if not q:
        raise ValueError("La pregunta RAG está vacía.")

    collection, chunks = ensure_rag_resources(reindex=False)
    _show = show_thinking if show_thinking is not None else sys.stdout.isatty()
    tty = sys.__stdout__

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            _run_rag_with_stdout_captured,
            collection,
            chunks,
            q,
            compress_with_llm=compress_with_llm,
        )
        if _show and tty.isatty():
            _spin_thinking_while(tty, future)
        return future.result()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG pipeline v2 — API + CLI (reindex como v1, consulta sin tocar v1)."
    )
    parser.add_argument(
        "--docs-dir",
        default="seed/manual/",
        help="Carpeta con documentos (solo si reindexas)",
    )
    parser.add_argument(
        "--con-compresion-llm",
        action="store_true",
        help="Activa compresión LLM intermedia antes de generar.",
    )
    parser.add_argument(
        "--query",
        default="",
        help="Una sola pregunta y salir (sin bucle interactivo).",
    )
    args = parser.parse_args()
    compress_with_llm: bool = args.con_compresion_llm

    print(f"\n{CYAN}{BOLD}{'=' * 80}")
    print("  RAG — Pipeline completo (v2 — API / CLI)")
    print(f"{'=' * 80}{RESET}")
    print(f"  {DIM}Índice:{RESET} {CHROMA_DIR}\n")

    if not os.environ.get("GROQ_API_KEY"):
        print(f"  {RED}{BOLD}ERROR: GROQ_API_KEY no configurada.{RESET}\n")
        return

    docs_dir = _normalize_docs_dir(args.docs_dir)

    ejecutar_pipeline = _preguntar_reindexar()
    try:
        ensure_rag_resources(reindex=ejecutar_pipeline, docs_dir=docs_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"  {RED}{e}{RESET}\n")
        return

    if args.query.strip():
        print(f"\n  {DIM}Ejecutando pipeline...{RESET}\n")
        try:
            answer = answer_rag_query(args.query.strip(), compress_with_llm=compress_with_llm)
            print(f"\n  {GREEN}{BOLD}Respuesta:{RESET}\n  {GREEN}{answer}{RESET}\n")
        except Exception as e:
            print(f"\n  {RED}Error: {e}{RESET}\n")
        return

    header("PASO 4", "Consultas — integrado", CYAN)
    print(f"\n  {GREEN}{BOLD}¡Listo!{RESET} {DIM}(salir para terminar){RESET}\n")

    while True:
        try:
            question = input(f"  {WHITE}{BOLD}Pregunta:{RESET} ").strip()
            if not question:
                continue
            if question.lower() in ("salir", "exit", "quit"):
                print(f"\n  {GREEN}¡Hasta luego!{RESET}\n")
                break
            print(f"\n  {DIM}Ejecutando pipeline...{RESET}\n")
            answer = answer_rag_query(question, compress_with_llm=compress_with_llm)
            print(f"\n  {GREEN}{BOLD}Respuesta:{RESET}\n  {GREEN}{answer}{RESET}\n")
            print(f"  {'-' * 80}\n")
        except KeyboardInterrupt:
            print(f"\n\n  {GREEN}¡Hasta luego!{RESET}\n")
            break
        except Exception as e:
            print(f"\n  {RED}Error: {e}{RESET}\n")


if __name__ == "__main__":
    main()
