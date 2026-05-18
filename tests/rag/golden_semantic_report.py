"""Acumula resultados por caso y escribe TXT de resumen al terminar pytest (append por ejecución)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_RECORDS: list["GoldenSemanticRow"] = []


@dataclass(frozen=True, slots=True)
class GoldenSemanticRow:
    case_id: str
    golden_set: str
    cosine: float
    umbral: float
    passed: bool


def clear_records() -> None:
    _RECORDS.clear()


def record_similarity_case(row: GoldenSemanticRow) -> None:
    _RECORDS.append(row)


def resolve_report_path(repo_root: Path) -> Path:
    env_path = os.environ.get("RAG_GOLDEN_SUMMARY_TXT", "").strip()
    if env_path:
        cand = Path(env_path)
        return cand if cand.is_absolute() else (repo_root / cand).resolve()
    return repo_root / "rag" / "fixtures" / "reports" / "golden_similarity_pytest_summary.txt"


def write_summary_txt(*, repo_root: Path) -> Path | None:
    threshold = float(os.environ.get("RAG_GOLDEN_MIN_COSINE", "0.65"))
    out_path = resolve_report_path(repo_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(UTC).isoformat()
    rows = list(_RECORDS)
    lines = [
        f"timestamp_utc={ts}",
        "# Resumen similitud coseno RAG vs golden (pytest)",
        f"umbral_cosine_minimo={threshold:.6f}",
        f"casos_ejecutados_con_metrica={len(rows)}",
    ]

    if not rows:
        lines.append(
            "nota=sin filas recolectadas (ej. skips, error antes del cálculo o suite distinta)."
        )
    else:
        passed_n = sum(1 for r in rows if r.passed)
        failed_n = len(rows) - passed_n
        lines.append(f"passed={passed_n}")
        lines.append(f"failed={failed_n}")

        cos_vals = [r.cosine for r in rows]
        cmin = min(cos_vals)
        cmax = max(cos_vals)

        def _near(tag: float, x: float) -> bool:
            return abs(x - tag) < 1e-6

        mins = sorted((r for r in rows if _near(cmin, r.cosine)), key=lambda x: (x.golden_set, x.case_id))
        maxs = sorted((r for r in rows if _near(cmax, r.cosine)), key=lambda x: (x.golden_set, x.case_id))
        for r in mins:
            lines.append(
                "min_cosine_detalle="
                f"cos={r.cosine:.6f}; case_id={r.case_id}; golden={r.golden_set}.jsonl; passed={'1' if r.passed else '0'}"
            )
        for r in maxs:
            lines.append(
                "max_cosine_detalle="
                f"cos={r.cosine:.6f}; case_id={r.case_id}; golden={r.golden_set}.jsonl; passed={'1' if r.passed else '0'}"
            )

        avg = sum(cos_vals) / len(rows)
        lines.append(f"promedio_cosine={avg:.6f}")

    separator = "=" * 78
    block = "\n".join([separator] + lines) + "\n"

    append_mode = os.environ.get("RAG_GOLDEN_SUMMARY_OVERWRITE", "").strip() != "1"
    if append_mode and out_path.exists() and out_path.stat().st_size > 0:
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write("\n")
            fh.write(block)
    else:
        out_path.write_text(block, encoding="utf-8")

    _RECORDS.clear()
    return out_path
