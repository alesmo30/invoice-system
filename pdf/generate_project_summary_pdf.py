"""
Genera PDF de documentación final del proyecto (resumen ejecutivo + técnico).

Incluye al final los diagramas de diagrams/ (render Mermaid -> PNG vía @mermaid-js/mermaid-cli).

Uso:
    python pdf/generate_project_summary_pdf.py
    python pdf/generate_project_summary_pdf.py -o docs/mi_resumen.pdf
    python pdf/generate_project_summary_pdf.py --skip-diagrams
"""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUTPUT = _REPO_ROOT / "docs" / "Invoice_System_Resumen_Proyecto.pdf"
_GOLDEN_REPORT = _REPO_ROOT / "rag" / "fixtures" / "reports" / "golden_similarity_pytest_summary.txt"
_DIAGRAMS_DIR = _REPO_ROOT / "diagrams"
_DIAGRAM_CACHE = _DIAGRAMS_DIR / "export" / "pdf_build"
_MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_MERMAID_CLI = "@mermaid-js/mermaid-cli@11.4.0"


def _safe(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u201c", '"').replace("\u201d", '"')
    return text.encode("latin-1", "replace").decode("latin-1")


def _read_last_golden_block() -> dict[str, str] | None:
    if not _GOLDEN_REPORT.is_file():
        return None
    raw = _GOLDEN_REPORT.read_text(encoding="utf-8")
    blocks = [b.strip() for b in raw.split("=" * 78) if b.strip()]
    if not blocks:
        return None
    last = blocks[-1]
    out: dict[str, str] = {}
    for line in last.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out or None


@dataclass(frozen=True)
class DiagramFigure:
    source_file: str
    section_title: str
    caption: str
    mermaid_code: str
    slug: str


def _slugify(text: str, *, max_len: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return (s[:max_len] or "fig").strip("_")


def _parse_diagrams_from_md(md_path: Path) -> list[DiagramFigure]:
    content = md_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    doc_title = lines[0].lstrip("# ").strip() if lines else md_path.stem
    figures: list[DiagramFigure] = []
    fig_idx = 0

    chunks = re.split(r"\n##\s+", content)
    if len(chunks) == 1:
        sections = [("Vista general", chunks[0])]
    else:
        sections = [("Introducción", chunks[0])]
        for chunk in chunks[1:]:
            sub = chunk.split("\n", 1)
            sections.append((sub[0].strip(), sub[1] if len(sub) > 1 else ""))

    for sec, block in sections:
        for match in _MERMAID_BLOCK_RE.finditer(block):
            fig_idx += 1
            code = match.group(1).strip()
            if not code:
                continue
            slug = f"{md_path.stem}_{fig_idx:02d}_{_slugify(sec)}"
            figures.append(
                DiagramFigure(
                    source_file=md_path.name,
                    section_title=sec,
                    caption=f"{doc_title} — {sec}",
                    mermaid_code=code,
                    slug=slug,
                )
            )
    return figures


def collect_diagram_figures() -> list[DiagramFigure]:
    figures: list[DiagramFigure] = []
    for md_path in sorted(_DIAGRAMS_DIR.glob("*.md")):
        if md_path.name.upper() == "README.MD":
            continue
        figures.extend(_parse_diagrams_from_md(md_path))
    return figures


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        f.read(8)
        head = f.read(8)
    if head[:4] != b"\x89PNG":
        return 1600, 900
    w, h = struct.unpack(">II", head[4:])
    return w or 1, h or 1


def _render_mermaid_png(mermaid_code: str, png_path: Path) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    mmd_path = png_path.with_suffix(".mmd")
    mmd_path.write_text(mermaid_code, encoding="utf-8")
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("npx no encontrado; instala Node.js para renderizar diagramas Mermaid.")
    cmd = [
        npx,
        "--yes",
        _MERMAID_CLI,
        "-i",
        str(mmd_path),
        "-o",
        str(png_path),
        "-w",
        "2000",
        "-b",
        "white",
    ]
    subprocess.run(cmd, check=True, cwd=str(_REPO_ROOT), timeout=180)


def render_diagram_assets(
    figures: list[DiagramFigure],
    *,
    cache_dir: Path | None = None,
    force: bool = False,
) -> list[tuple[DiagramFigure, Path]]:
    cache = cache_dir or _DIAGRAM_CACHE
    cache.mkdir(parents=True, exist_ok=True)
    rendered: list[tuple[DiagramFigure, Path]] = []
    for fig in figures:
        png_path = cache / f"{fig.slug}.png"
        if force or not png_path.is_file():
            print(f"  Renderizando {fig.source_file} / {fig.section_title} -> {png_path.name}")
            _render_mermaid_png(fig.mermaid_code, png_path)
        rendered.append((fig, png_path))
    return rendered


class SummaryPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, _safe(f"Página {self.page_no()}"), align="C")

    def add_title_page(self, subtitle: str, date_str: str) -> None:
        self.add_page()
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(30, 30, 30)
        self.ln(35)
        self.multi_cell(0, 12, _safe("Invoice System"), align="C")
        self.set_font("Helvetica", "", 14)
        self.ln(4)
        self.multi_cell(0, 8, _safe("Apple Store Analytics"), align="C")
        self.ln(10)
        self.set_font("Helvetica", "I", 11)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 7, _safe(subtitle), align="C")
        self.ln(20)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, _safe(f"Documentación generada: {date_str}"), align="C")

    def section(self, title: str) -> None:
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 8, _safe(title))
        self.set_draw_color(20, 60, 120)
        y = self.get_y()
        self.line(10, y, 200, y)
        self.ln(3)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)

    def body(self, text: str) -> None:
        self.set_x(self.l_margin)
        self.multi_cell(0, 5.5, _safe(text))
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_x(self.l_margin)
        self.multi_cell(0, 5.5, _safe(f"- {text}"))

    def add_diagram_figure(self, fig: DiagramFigure, png_path: Path, figure_no: int) -> None:
        self.add_page()
        self.section(f"Figura {figure_no}. {fig.caption}")
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(90, 90, 90)
        self.body(f"Fuente: diagrams/{fig.source_file}")
        self.ln(2)

        max_w = self.w - self.l_margin - self.r_margin
        max_h = self.h - self.get_y() - self.b_margin - 8
        w_px, h_px = _png_dimensions(png_path)
        aspect = h_px / w_px
        img_w = max_w
        img_h = img_w * aspect
        if img_h > max_h:
            img_h = max_h
            img_w = img_h / aspect

        x = self.l_margin + (max_w - img_w) / 2
        self.image(str(png_path), x=x, y=self.get_y(), w=img_w, h=img_h)
        self.set_y(self.get_y() + img_h + 4)


def _add_main_content(pdf: SummaryPDF, golden: dict[str, str] | None) -> None:
    pdf.add_page()
    pdf.section("1. Visión del proyecto")
    pdf.body(
        "Sistema de gestión y analítica para un retail tipo Apple Store. Combina datos "
        "transaccionales en PostgreSQL (Supabase + Prisma), consultas en lenguaje natural "
        "sobre la base de datos, un pipeline RAG sobre manuales operativos en Markdown, y "
        "un supervisor multi-agente (LangGraph) con revisión humana (HITL) y generación de "
        "cotizaciones en PDF."
    )

    pdf.section("2. Stack tecnológico")
    for item in [
        "Python 3.13+, Prisma Client Python, Supabase (PostgreSQL).",
        "ChromaDB local (chroma_db_pipeline_completo/) + sentence-transformers + rank-bm25.",
        "LangChain / LangGraph; LLM vía Groq (supervisor, RAG, ReAct) y Gemini opcional.",
        "Ragas 0.4.3 (TestsetGenerator) para golden dataset sintético.",
        "pytest + similitud coseno (embeddings locales) para evaluar respuestas RAG.",
        "fpdf2 para cotizaciones aprobadas y este documento de resumen.",
    ]:
        pdf.bullet(item)

    pdf.section("3. Capa de datos")
    pdf.body("Esquema principal (Prisma):")
    for item in [
        "employees — personal de tienda.",
        "customers — compradores.",
        "products — catálogo Apple (SKU, categoría, unit_price en USD).",
        "invoices e invoice_items — ventas y líneas de detalle.",
    ]:
        pdf.bullet(item)
    pdf.body(
        "Seeds: productos, empleados, clientes y facturas de muestra (python -m seed.load_seed). "
        "CRUD centralizado en crud/prisma_crud.py."
    )

    pdf.section("4. Pipeline RAG (rag.main_rag_pipeline_v2)")
    pdf.body(
        "Corpus por defecto: seed/manual/ (devoluciones, solicitudes-clientes, soporte-tecnico). "
        "Flujo: carga de documentos, chunking por párrafos, indexación en Chroma, recuperación "
        "avanzada (advanced_rag_query) y síntesis con Groq. API programática: answer_rag_query()."
    )
    pdf.bullet("Índice persistente: chroma_db_pipeline_completo/, colección rag_pipeline_completo.")
    pdf.bullet("Embeddings: paraphrase-multilingual-MiniLM-L12-v2 (mismo modelo en tests golden).")

    pdf.section("5. Supervisor multi-agente (agents.playground.supervisor)")
    pdf.body("Grafo LangGraph con clasificación en una sola categoría por mensaje:")
    pdf.bullet("cotizacion — presupuesto con productos y cantidades.")
    pdf.bullet("db_query — ventas, inventario, clientes (ReAct + SQL solo lectura).")
    pdf.bullet("rag_query — políticas y procedimientos según manuales.")
    pdf.bullet("greeting — saludo sin consulta de negocio.")
    pdf.body(
        "Verificador de confianza (umbral 0.99): si falla, interrupt HITL para corrección humana. "
        "Cotización: ReAct sobre products, revisión vendedor (HITL), PDF opcional al aprobar."
    )
    pdf.body("CLI interactivo: python -m agents.playground.supervisor")

    pdf.section("6. Evaluación y calidad RAG")
    pdf.body("Generación golden (Ragas TestsetGenerator):")
    pdf.bullet("python -m rag.generate_golden_ragas --per-document --docs-dir seed/manual/")
    pdf.bullet("Salida: rag/fixtures/golden/*.jsonl (~17 preguntas/documento).")
    pdf.body("Métricas Ragas opcionales en supervisor: RAG_FAITHFULNESS, RAG_CONTEXT_PRECISION.")
    pdf.body(
        "pytest golden (RUN_RAG_GOLDEN=1): compara embedding(reference) vs embedding(respuesta RAG); "
        "umbral RAG_GOLDEN_MIN_COSINE (default 0.65). Reporte: rag/fixtures/reports/"
        "golden_similarity_pytest_summary.txt"
    )

    if golden:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.body("Última corrida registrada en reporte golden:")
        pdf.set_font("Helvetica", "", 9)
        for key in (
            "timestamp_utc",
            "casos_ejecutados_con_metrica",
            "passed",
            "failed",
            "promedio_cosine",
            "umbral_cosine_minimo",
        ):
            if key in golden:
                pdf.bullet(f"{key}: {golden[key]}")

    pdf.section("7. Estructura del repositorio (resumen)")
    for item in [
        "agents/playground/ — supervisor, db_react_agent, quote_react_agent, interactive_chat.",
        "rag/ — ingestion, retrieval, vectorstore, pipelines, generate_golden_ragas, run_ragas_eval.",
        "seed/manual/ — documentación fuente RAG.",
        "tests/rag/ — test_golden_semantic_similarity.py.",
        "diagrams/ — diagramas Mermaid (anexo visual al final de este PDF).",
        "pdf/ — generación cotizaciones y este resumen.",
    ]:
        pdf.bullet(item)

    pdf.section("8. Comandos esenciales")
    for cmd in [
        "pip install -r requirements.txt && prisma generate",
        "python connection/prisma_connection_test.py",
        "python -m seed.load_seed",
        "python -m rag.main_rag_pipeline_v2",
        "RUN_RAG_GOLDEN=1 pytest tests/rag/test_golden_semantic_similarity.py -v",
        "python -m agents.playground.supervisor",
    ]:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Courier", "", 8)
        pdf.multi_cell(0, 4.5, _safe(cmd))
        pdf.set_font("Helvetica", "", 10)

    pdf.section("9. Estado del roadmap")
    for item in [
        "[Completado] Supabase, Prisma, seeds, RAG + Chroma, supervisor LangGraph, golden Ragas + pytest.",
        "[Pendiente] Datos sintéticos extensos (30 días) y pipeline JSON / diarios narrativos.",
    ]:
        pdf.bullet(item)

    pdf.section("10. Licencia")
    pdf.body("MIT — ver README.md en la raíz del repositorio.")


def _add_diagram_appendix(pdf: SummaryPDF, rendered: list[tuple[DiagramFigure, Path]]) -> None:
    pdf.add_page()
    pdf.section("Anexo A — Diagramas de arquitectura")
    pdf.body(
        "Las siguientes figuras corresponden a los diagramas Mermaid de la carpeta diagrams/. "
        "Se generan automáticamente al construir este PDF (requiere Node.js y npx)."
    )
    pdf.body(
        "Orden sugerido para presentación: RAG stack (03), supervisor (01), golden pytest (02), "
        "ReAct BD/cotización (04)."
    )
    for idx, (fig, png_path) in enumerate(rendered, start=1):
        pdf.add_diagram_figure(fig, png_path, idx)


def build_pdf(
    output_path: Path,
    *,
    include_diagrams: bool = True,
    force_diagram_render: bool = False,
) -> Path:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    golden = _read_last_golden_block()

    pdf = SummaryPDF()
    pdf.add_title_page(
        "Resumen general del proyecto — documentación final",
        now,
    )
    _add_main_content(pdf, golden)

    if include_diagrams:
        figures = collect_diagram_figures()
        if not figures:
            print("Aviso: no se encontraron bloques mermaid en diagrams/", file=sys.stderr)
        else:
            print(f"Renderizando {len(figures)} diagrama(s) Mermaid...")
            try:
                rendered = render_diagram_assets(figures, force=force_diagram_render)
                _add_diagram_appendix(pdf, rendered)
            except Exception as exc:
                print(f"Error al renderizar diagramas: {exc}", file=sys.stderr)
                print("Generando PDF sin anexo visual. Usa --skip-diagrams para omitir.", file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera PDF resumen del proyecto.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Ruta del PDF (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--skip-diagrams",
        action="store_true",
        help="No incluir anexo de diagramas (solo texto).",
    )
    parser.add_argument(
        "--force-diagrams",
        action="store_true",
        help="Volver a renderizar PNG aunque existan en diagrams/export/pdf_build/.",
    )
    args = parser.parse_args()
    path = build_pdf(
        args.output.resolve(),
        include_diagrams=not args.skip_diagrams,
        force_diagram_render=args.force_diagrams,
    )
    print(f"PDF generado: {path}")


if __name__ == "__main__":
    main()
