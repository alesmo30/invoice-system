"""
generate_golden_ragas.py — Genera un golden dataset sintético usando Ragas 0.4.3.

Modo directorio único (todos los documentos juntos):
    python -m rag.generate_golden_ragas --output rag/fixtures/rag_golden.jsonl --num-samples 10

Modo un JSONL por archivo (recomendado; ~15–20 preguntas por documento por defecto):
    python -m rag.generate_golden_ragas --per-document --docs-dir seed/manual/ --output-dir rag/fixtures/golden/

Requirements: GROQ_API_KEY; ``rapidfuzz`` y dependencias Ragas en requirements.txt.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ~15–20 por documento según tamaño típico del manual; Ragas puede devolver +/- filas.
_DEFAULT_SAMPLES_SINGLE_FILE = 17

_SPANISH_LLM_CONTEXT = """Eres un generador de datos de evaluación para un sistema RAG. Los usuarios \
formulan preguntas en español.

Reglas obligatorias:
- Todas las user_input deben estar en español profesional (Colombia / Latinoamérica).
- Todas las reference deben estar en español, ser precisas y ancladas al texto fuente \
(sin inventar información que no figure en los documentos).
- Prioriza formulaciones DETALLADAS y específicas: plazos, montos, excepciones, procedimientos. \
Combina preguntas de un único párrafo/sección con otras multi-hop cuando el contenido lo permita.
- Sin saludos ni preámbulos; solo la pregunta o la respuesta de referencia.
- Puedes conservar marcas comerciales o nombres de productos tal como aparecen en el texto."""


def _get_langchain_documents(docs_dir: str) -> list:
    """Carga documentos del corpus y los convierte a LangChain Document."""
    from rag.ingestion import load_directory

    documents = load_directory(docs_dir)

    from langchain_core.documents import Document as LangChainDocument

    return [
        LangChainDocument(page_content=doc.content, metadata=dict(doc.metadata))
        for doc in documents
    ]


def _path_to_langchain_document(path: Path):
    """Carga un único archivo soportado (ingestion) como LangChain Document."""
    from langchain_core.documents import Document as LangChainDocument
    from rag.ingestion import LOADERS, load_document

    if path.suffix.lower() not in LOADERS:
        raise ValueError(f"Extensión no soportada: {path.suffix}")

    doc = load_document(str(path))
    meta = dict(doc.metadata)
    meta["source"] = str(path.resolve())
    return LangChainDocument(page_content=doc.content, metadata=meta)


def _iter_corpus_files(docs_dir: Path) -> list[Path]:
    from rag.ingestion import LOADERS

    exts = set(LOADERS.keys())
    return sorted(
        p for p in docs_dir.iterdir() if p.is_file() and p.suffix.lower() in exts
    )


def _get_ragas_llm():
    from langchain_groq import ChatGroq
    from ragas.llms import LangchainLLMWrapper

    from rag.ragas_eval_llm import groq_check_model_name

    llm = ChatGroq(model=groq_check_model_name())
    return LangchainLLMWrapper(llm)


def _get_ragas_embeddings():
    from ragas.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )


def _build_generator(*, llm_context: str | None = None):
    from ragas.testset import TestsetGenerator

    return TestsetGenerator(
        llm=_get_ragas_llm(),
        embedding_model=_get_ragas_embeddings(),
        llm_context=llm_context,
    )


def _rows_from_testset(generator, lc_documents: list, num_samples: int) -> list[dict]:
    if not lc_documents:
        raise ValueError("No hay documentos para generar el testset.")
    logger.info(
        "Generando %s muestras sobre %s documento(s)...",
        num_samples,
        len(lc_documents),
    )
    testset = generator.generate_with_langchain_docs(
        lc_documents,
        testset_size=num_samples,
    )
    rows = testset.to_list()
    if len(rows) != num_samples:
        logger.warning(
            "Ragas devolvió %d filas (solicitadas %d); se escriben todas.",
            len(rows),
            num_samples,
        )
    return rows


def _write_jsonl(
    rows: list[dict],
    output_path: Path,
    *,
    source_slug: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    slug_safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in source_slug)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, raw in enumerate(rows):
            row = dict(raw)
            synthesizer_name = row.pop("synthesizer_name", "") or ""
            user_input = row.pop("user_input", None) or ""
            reference = row.pop("reference", None) or ""
            reference_contexts = row.pop("reference_contexts", None) or []
            if isinstance(reference_contexts, str):
                reference_contexts = [reference_contexts]
            meta = dict(row)
            meta["synthesizer_name"] = synthesizer_name
            meta["source_document"] = slug_safe
            record = {
                "id": f"{slug_safe}_{i + 1}",
                "user_input": user_input,
                "reference": reference,
                "reference_contexts": list(reference_contexts),
                "metadata": meta,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def generate_golden_testset(
    docs_dir: str,
    output_path: str,
    num_samples: int = _DEFAULT_SAMPLES_SINGLE_FILE,
    seed: int | None = None,
    *,
    llm_context: str | None = _SPANISH_LLM_CONTEXT,
) -> None:
    """Un solo JSONL a partir de todo el contenido del directorio."""
    if seed is not None:
        import random

        random.seed(seed)

    logger.info("Cargando documentos desde: %s", docs_dir)
    documents = _get_langchain_documents(docs_dir)
    logger.info("Cargados %d documentos", len(documents))

    generator = _build_generator(llm_context=llm_context)
    rows = _rows_from_testset(generator, documents, num_samples)

    out = Path(output_path)
    if not out.is_absolute():
        out = _REPO_ROOT / out
    stem = Path(docs_dir).resolve().name
    _write_jsonl(rows, out, source_slug=stem)
    logger.info("Golden dataset guardado en: %s", out)


def generate_golden_per_document(
    docs_dir: str,
    output_dir: str,
    num_samples: int = _DEFAULT_SAMPLES_SINGLE_FILE,
    seed: int | None = None,
    *,
    llm_context: str | None = _SPANISH_LLM_CONTEXT,
) -> list[Path]:
    """Un JSONL por archivo bajo ``docs_dir``."""
    if seed is not None:
        import random

        random.seed(seed)

    root = Path(docs_dir)
    if not root.is_absolute():
        root = _REPO_ROOT / root
    if not root.is_dir():
        raise FileNotFoundError(f"No se encontró el directorio: {root}")

    out_dir = Path(output_dir)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir

    files = _iter_corpus_files(root)
    if not files:
        raise FileNotFoundError(f"No hay .md/.txt/.pdf en: {root}")

    logger.info(
        "Modo por documento: %s archivos, %s muestras c/u → %s",
        len(files),
        num_samples,
        out_dir,
    )

    generator = _build_generator(llm_context=llm_context)
    written: list[Path] = []

    for path in files:
        slug = path.stem
        lc = _path_to_langchain_document(path)
        rows = _rows_from_testset(generator, [lc], num_samples)
        target = out_dir / f"{slug}.jsonl"
        _write_jsonl(rows, target, source_slug=slug)
        written.append(target)
        logger.info("  Escrito %s (%d filas)", target.name, len(rows))

    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera golden dataset con Ragas 0.4.3 (español por defecto)."
    )
    parser.add_argument(
        "--docs-dir",
        default="seed/manual/",
        help="Directorio con documentos fuente (default: seed/manual/)",
    )
    parser.add_argument(
        "--output",
        default="rag/fixtures/rag_golden.jsonl",
        help="JSONL único si no usas --per-document (default: rag/fixtures/rag_golden.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        default="rag/fixtures/golden/",
        help="Directorio de salida con --per-document (default: rag/fixtures/golden/)",
    )
    parser.add_argument(
        "--per-document",
        action="store_true",
        help="Genera un .jsonl por archivo en docs-dir",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=_DEFAULT_SAMPLES_SINGLE_FILE,
        help=f"Muestras por generación (default: {_DEFAULT_SAMPLES_SINGLE_FILE}, rango recomendado 15–20)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semilla para reproducibilidad (opcional)",
    )
    parser.add_argument(
        "--no-spanish-context",
        action="store_true",
        help="No inyectar llm_context en español (solo para pruebas)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Logging INFO",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY no configurada.", file=sys.stderr)
        sys.exit(1)

    ctx = None if args.no_spanish_context else _SPANISH_LLM_CONTEXT

    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_absolute():
        docs_dir = _REPO_ROOT / docs_dir

    if not docs_dir.is_dir():
        print(f"ERROR: No se encontró el directorio: {docs_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.per_document:
            paths = generate_golden_per_document(
                docs_dir=str(docs_dir),
                output_dir=args.output_dir,
                num_samples=args.num_samples,
                seed=args.seed,
                llm_context=ctx,
            )
            for p in paths:
                print(f"✓ {p}")
        else:
            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = _REPO_ROOT / output_path
            generate_golden_testset(
                docs_dir=str(docs_dir),
                output_path=str(output_path),
                num_samples=args.num_samples,
                seed=args.seed,
                llm_context=ctx,
            )
            print(f"✓ Golden dataset generado: {output_path}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        logger.exception("Error generando golden dataset")
        sys.exit(1)


if __name__ == "__main__":
    main()
