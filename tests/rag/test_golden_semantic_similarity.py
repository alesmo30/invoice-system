"""
Similitud coseno (embeddings locales) entre la respuesta del RAG y ``reference`` del golden.

Ejecución::
    RUN_RAG_GOLDEN=1 pytest tests/rag/test_golden_semantic_similarity.py -v \\
        --log-cli-level=INFO --log-cli-format="%(message)s"

Umbral (default 0.65), calíbralo según tus corridas::
    RAG_GOLDEN_MIN_COSINE=0.72

Con ``RUN_RAG_GOLDEN=1`` pytest **añade** bloques a ``rag/fixtures/reports/golden_similarity_pytest_summary.txt``
(separados por ``timestamp_utc`` y una línea ``====...``). Sobrescribir todo el archivo: ``RAG_GOLDEN_SUMMARY_OVERWRITE=1``.
Override path: ``RAG_GOLDEN_SUMMARY_TXT``.

Sin ``RUN_RAG_GOLDEN=1``: todos skipped. Falta ``GROQ_API_KEY``: comprueba ``.env`` en la raíz
(``tests/conftest.py`` llama ``load_dotenv`` al arrancar pytest). Para el motivo completo:
``pytest -rs``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from tests.rag.golden_semantic_report import GoldenSemanticRow, record_similarity_case

logger = logging.getLogger("rag_golden_semantic")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_DIR = _REPO_ROOT / "rag" / "fixtures" / "golden"


def _load_all_golden_cases() -> list[tuple[str, str, str, str]]:
    """Tuplas: case_id, user_input, reference, stem del archivo golden."""
    if not _GOLDEN_DIR.is_dir():
        return []
    cases: list[tuple[str, str, str, str]] = []
    for path in sorted(_GOLDEN_DIR.glob("*.jsonl")):
        stem = path.stem
        row_num = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                user_input = (obj.get("user_input") or "").strip()
                reference = (obj.get("reference") or "").strip()
                cid = (obj.get("id") or "").strip()
                row_num += 1
                if not cid:
                    cid = f"{stem}_{row_num}"
                if not user_input or not reference:
                    continue
                cases.append((cid, user_input, reference, stem))
    return cases


_GOLDEN_CASES = _load_all_golden_cases()

_MIN_COSINE = float(os.environ.get("RAG_GOLDEN_MIN_COSINE", "0.65"))


def _chroma_ready() -> bool:
    chroma_abs = _REPO_ROOT / "chroma_db_pipeline_completo"
    return chroma_abs.is_dir()


def _should_skip_gate() -> str | None:
    if os.environ.get("RUN_RAG_GOLDEN", "").strip() != "1":
        return "RUN_RAG_GOLDEN=1 para ejecutar estos tests."
    if not os.environ.get("GROQ_API_KEY"):
        return "GROQ_API_KEY no configurada (generación del RAG)."
    if not _chroma_ready():
        return (
            f"Índice Chroma no encontrado en "
            f"{_REPO_ROOT / 'chroma_db_pipeline_completo'}."
        )
    if not _GOLDEN_CASES:
        return f"No hay casos en {_GOLDEN_DIR} (*.jsonl)."
    return None


pytestmark = pytest.mark.rag_golden

_placeholder = ("__empty__", "", "", "")


@pytest.mark.parametrize(
    ("case_id", "question", "reference", "golden_stem"),
    _GOLDEN_CASES if _GOLDEN_CASES else [_placeholder],
    ids=[
        (
            f"{stem}::{cid}"
            if stem
            else cid
        )
        for cid, _, _, stem in (_GOLDEN_CASES if _GOLDEN_CASES else [_placeholder])
    ],
)
def test_rag_answer_semantic_near_golden(
    case_id: str,
    question: str,
    reference: str,
    golden_stem: str,
) -> None:
    reason = _should_skip_gate()
    if reason:
        pytest.skip(reason)

    if case_id == "__empty__":
        pytest.skip("No hay líneas válidas en golden JSONL.")

    from rag.embeddings import cosine_similarity, get_embeddings_batch
    from rag.main_rag_pipeline_v2 import answer_rag_query

    raw = answer_rag_query(question, compress_with_llm=False, show_thinking=False)
    assert isinstance(raw, str), "Sin return_contexts la salida debe ser str."
    ans = raw.strip()
    assert ans, f"Respuesta vacía ({case_id})"

    embeddings = get_embeddings_batch([reference, ans])
    sim = cosine_similarity(embeddings[0], embeddings[1])

    logger.info(
        "%s cosine=%.4f min=%.2f [%s]",
        case_id,
        sim,
        _MIN_COSINE,
        golden_stem,
    )

    passed_gate = sim >= _MIN_COSINE
    record_similarity_case(
        GoldenSemanticRow(
            case_id=case_id,
            golden_set=golden_stem,
            cosine=float(sim),
            umbral=float(_MIN_COSINE),
            passed=passed_gate,
        )
    )

    assert passed_gate, (
        f"Similitud coseno mín {_MIN_COSINE:.2f}; obtuvo {sim:.4f}\n"
        f"case={case_id} archivo={golden_stem}.jsonl\n"
        f"P: {question[:240]}...\n"
        f"reference[:240]={reference[:240]}...\n"
        f"answer[:240]={ans[:240]}...\n"
    )
