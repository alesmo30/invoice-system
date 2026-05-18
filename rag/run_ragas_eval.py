"""
Evaluación RAGAS (Faithfulness, Context precision) con GROQ_MODEL_CHECK.

Uso:
  python -m rag.run_ragas_eval
  python -m rag.run_ragas_eval --live --question "¿Cuál es la política de garantía?"
  python -m rag.run_ragas_eval --doc-context-precision
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _demo_rows() -> list[dict[str, Any]]:
    return [
        {
            "user_input": "¿De qué trata el manual?",
            "response": "No tengo suficiente información.",
            "retrieved_contexts": [
                "Capítulo 1. Este manual describe procedimientos de garantía para productos Apple."
            ],
        },
        {
            "user_input": "¿De qué trata el manual?",
            "response": "Describe procedimientos de garantía para productos Apple.",
            "retrieved_contexts": [
                "Capítulo 1. Este manual describe procedimientos de garantía para productos Apple."
            ],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAGAS metrics (Faithfulness, Context precision) con GROQ_MODEL_CHECK."
    )
    parser.add_argument(
        "--doc-context-precision",
        action="store_true",
        help="Ejemplo ContextPrecision con reference (como en la documentación RAGAS)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Ejecutar answer_rag_query y puntuar con Faithfulness + context precision (sin ref.)",
    )
    parser.add_argument(
        "--question",
        default="¿Cuál es el procedimiento de devolución?",
        help="Pregunta para --live",
    )
    args = parser.parse_args()

    if not os.environ.get("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY no configurada.")

    from rag.ragas_eval_llm import (
        compute_context_precision_from_response_score,
        compute_context_precision_with_reference_score,
        compute_faithfulness_score,
        groq_check_model_name,
    )

    print(f"Evaluador RAGAS: modelo {groq_check_model_name()}\n")

    if args.doc_context_precision:
        s = compute_context_precision_with_reference_score(
            user_input="Where is the Eiffel Tower located?",
            reference="The Eiffel Tower is located in Paris.",
            retrieved_contexts=[
                "The Eiffel Tower is located in Paris.",
                "The Brandenburg Gate is located in Berlin.",
            ],
        )
        print(f"Context precision (con reference, doc RAGAS): {s}\n")
        return

    rows: list[dict[str, Any]]
    if args.live:
        from rag.main_rag_pipeline_v2 import answer_rag_query

        q = args.question.strip()
        raw = answer_rag_query(q, compress_with_llm=False, return_contexts=True)
        if isinstance(raw, tuple):
            ans, ctxs = raw
        else:
            ans, ctxs = raw, []
        rows = [{"user_input": q, "response": ans, "retrieved_contexts": ctxs}]
    else:
        rows = _demo_rows()

    for i, row in enumerate(rows):
        fw = compute_faithfulness_score(
            row["user_input"],
            row["response"],
            row["retrieved_contexts"],
        )
        cp = compute_context_precision_from_response_score(
            row["user_input"],
            row["response"],
            row["retrieved_contexts"],
        )
        print(f"[{i}] faithfulness={fw}  context_precision (sin ref.)={cp}")
        print(f"    Q: {row['user_input'][:80]}...")
        print(f"    A: {str(row['response'])[:120]}...")
        print()


if __name__ == "__main__":
    main()
