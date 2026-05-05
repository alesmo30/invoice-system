import os
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF


def _pdf_safe(text: str) -> str:
    """Helvetica (latin-1) no cubre rayas tipográficas usadas en Markdown."""
    if not text:
        return ""
    return text.replace("\u2014", "-").replace("\u2013", "-")


def match_md_kv_bullet_line(line: str) -> tuple[str, str] | None:
    """
    Metadatos tipo lista del Markdown de cotización.

    Formato principal (quote_react_agent): - **Solicitante:** Juan → clave entre ** ** y cierre :**
    Forma alternativa: - **Solicitante** valor (algunos editores).
    Acepta viñetas -, –, —, •.
    """
    s = line.strip()
    m = re.match(r"^[-\u2013\u2014•]\s*\*\*([^*]+):\*\*\s*(.+)$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^[-\u2013\u2014•]\s*\*\*([^*]+)\*\*:\s*(.+)$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None


def _party_field_display(raw: str | None) -> str:
    """Nombre visible en PDF: '-' solo si no hay dato (incluye — / – del Markdown)."""
    s = _pdf_safe((raw or "").strip())
    if not s:
        return "-"
    if s in ("-", "—", "–"):
        return "-"
    if s.lower() in ("n/a", "na"):
        return "-"
    return s


class InvoicePDF(FPDF):
    PRIMARY_COLOR = (0, 51, 102)
    ACCENT_COLOR = (240, 245, 250)
    TEXT_COLOR = (40, 40, 40)
    MUTED_COLOR = (120, 120, 120)

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(*self.MUTED_COLOR)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def parse_markdown_invoice(md_text: str) -> dict:
    result = {"items": [], "metadata": {}, "notes": "", "footer": ""}

    lines = md_text.strip().split("\n")
    in_items = False
    in_notes = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_items:
                in_items = False
            continue

        if line.startswith("## "):
            result["metadata"]["title"] = line[3:]
        elif "**" in line:
            if "| Producto" in line and "SKU" in line:
                in_items = True
                continue
            elif in_items:
                if line.startswith("|") and "---" not in line:
                    parts = [p.strip() for p in line.split("|")[1:-1]]
                    if len(parts) >= 5 and parts[0]:
                        try:
                            result["items"].append({
                                "product": parts[0],
                                "sku": parts[1],
                                "quantity": int(parts[2]),
                                "unit_price": Decimal(parts[3].replace(",", "")),
                                "subtotal": Decimal(parts[4].replace(",", ""))
                            })
                        except (ValueError, IndexError):
                            in_items = False
                elif line.startswith("-"):
                    in_items = False
                    in_notes = True

            kv = match_md_kv_bullet_line(line)
            if kv:
                key, value = kv
                result["metadata"][key.lower()] = value

            if in_notes:
                if line.startswith("**Notas:**"):
                    result["notes"] = line.replace("**Notas:**", "").strip()
                elif line.startswith("- **"):
                    match = re.match(r"-\s*\*(.+?)\*:\s*(.+)", line)
                    if match:
                        result["metadata"][match.group(1).lower()] = match.group(2)
                elif line.startswith("*Precios"):
                    result["footer"] = line.replace("*", "").strip()
                elif line.startswith("---"):
                    in_notes = False

    result["subtotal"] = sum(item["subtotal"] for item in result["items"])
    result["total"] = result["subtotal"]

    return result


def generate_invoice_pdf(invoice_data: dict, output_path: str, logo_path: str = None) -> None:
    pdf = InvoicePDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)

    currency = invoice_data.get("currency", "USD")

    # Header bar
    pdf.set_fill_color(*InvoicePDF.PRIMARY_COLOR)
    pdf.rect(0, 0, 210, 35, style="F")

    if logo_path:
        pdf.image(logo_path, 15, 8, 25)

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 24)
    pdf.set_xy(45, 10)
    pdf.cell(120, 15, invoice_data.get("metadata", {}).get("title", "COTIZACIÓN"), align="L")

    pdf.set_font("helvetica", "", 10)
    pdf.set_xy(140, 12)
    pdf.cell(55, 6, f"#{invoice_data.get('invoice_number', '0001')}", align="R")

    pdf.set_y(40)
    pdf.set_text_color(*InvoicePDF.TEXT_COLOR)

    # Metadata row
    meta = invoice_data.get("metadata", {})
    pdf.set_font("helvetica", "", 10)
    meta_y = pdf.get_y()

    pdf.set_fill_color(*InvoicePDF.ACCENT_COLOR)
    pdf.rect(20, meta_y, 170, 25, style="F")

    pdf.set_xy(25, meta_y + 5)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(50, 5, f"Solicitante: {meta.get('solicitante', 'N/A')}")
    pdf.cell(50, 5, f"Vendedor: {meta.get('vendedor', 'N/A')}", align="R")

    pdf.set_xy(25, meta_y + 13)
    pdf.cell(50, 5, f"Fecha: {meta.get('fecha', datetime.now().strftime('%Y-%m-%d'))}")
    pdf.cell(50, 5, f"Moneda: {meta.get('moneda', currency)}", align="R")

    pdf.set_y(meta_y + 30)

    # Table header
    pdf.set_fill_color(*InvoicePDF.PRIMARY_COLOR)
    pdf.rect(20, pdf.get_y(), 170, 10, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_xy(22, pdf.get_y() + 2)
    pdf.cell(60, 6, "Producto")
    pdf.cell(35, 6, "SKU")
    pdf.cell(15, 6, "Cant.", align="R")
    pdf.cell(25, 6, "P. Unit.", align="R")
    pdf.cell(25, 6, "Subtotal", align="R")
    pdf.set_y(pdf.get_y() + 10)
    pdf.set_text_color(*InvoicePDF.TEXT_COLOR)

    # Table rows
    pdf.set_font("helvetica", "", 9)
    for i, item in enumerate(invoice_data.get("items", [])):
        if i % 2 == 0:
            pdf.set_fill_color(250, 250, 250)
            pdf.rect(20, pdf.get_y(), 170, 10, style="F")

        pdf.set_xy(22, pdf.get_y() + 2)
        pdf.cell(60, 6, item["product"][:30])
        pdf.cell(35, 6, item["sku"])
        pdf.cell(15, 6, str(item["quantity"]), align="R")
        pdf.cell(25, 6, f"{item['unit_price']:.2f}", align="R")
        pdf.cell(25, 6, f"{item['subtotal']:.2f}", align="R")
        pdf.set_y(pdf.get_y() + 10)

    # Totals
    pdf.set_y(pdf.get_y() + 5)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_xy(120, pdf.get_y())
    pdf.cell(45, 8, f"Subtotal ({currency}):", align="R")
    pdf.cell(25, 8, f"{invoice_data.get('subtotal', 0):.2f}", align="R")

    pdf.set_y(pdf.get_y() + 10)
    pdf.set_fill_color(*InvoicePDF.PRIMARY_COLOR)
    pdf.rect(115, pdf.get_y() - 3, 75, 12, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.cell(45, 8, f"Total ({currency}):", align="R")
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(25, 8, f"{invoice_data.get('total', 0):.2f}", align="R")
    pdf.set_text_color(*InvoicePDF.TEXT_COLOR)

    # Notes
    notes = invoice_data.get("notes", "")
    if notes:
        pdf.set_y(pdf.get_y() + 15)
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(0, 6, "Notas:")
        pdf.set_y(pdf.get_y() + 6)
        pdf.set_font("helvetica", "", 9)
        pdf.multi_cell(170, 5, notes)

    # Footer
    pdf.set_y(-20)
    pdf.set_font("helvetica", "I", 7)
    pdf.set_text_color(*InvoicePDF.MUTED_COLOR)
    pdf.cell(0, 5, invoice_data.get("footer", ""), align="C")

    pdf.output(output_path)
    print(f"PDF guardado: {output_path}")


# ─── Cotización aprobada (Markdown de quote_react_agent + empresa) ──────────


@dataclass(frozen=True)
class CompanyProfile:
    """Datos de empresa para el PDF; desde variables de entorno QUOTE_COMPANY_*."""

    trade_name: str
    legal_name: str
    tax_id: str
    address: str
    phone: str
    email: str
    website: str

    @classmethod
    def from_env(cls) -> "CompanyProfile":
        return cls(
            trade_name=os.getenv("QUOTE_COMPANY_TRADE_NAME", "").strip(),
            legal_name=os.getenv("QUOTE_COMPANY_LEGAL_NAME", "").strip(),
            tax_id=os.getenv("QUOTE_COMPANY_TAX_ID", "").strip(),
            address=os.getenv("QUOTE_COMPANY_ADDRESS", "").strip(),
            phone=os.getenv("QUOTE_COMPANY_PHONE", "").strip(),
            email=os.getenv("QUOTE_COMPANY_EMAIL", "").strip(),
            website=os.getenv("QUOTE_COMPANY_WEBSITE", "").strip(),
        )


def _parse_money_value(raw: str) -> Decimal | None:
    s = raw.strip().replace(",", "")
    try:
        return Decimal(s)
    except Exception:
        return None


def parse_quote_agent_markdown(md: str) -> dict[str, Any]:
    """
    Parsea el Markdown emitido por format_cotizacion_markdown (quote_react_agent).
    Tolera borradores sin tabla completa.
    """
    text = (md or "").replace("\r\n", "\n").strip()
    lines = text.split("\n")
    meta_flat: dict[str, str] = {}
    title = "Cotización"
    items: list[dict[str, Any]] = []
    notas = ""
    advertencias: list[str] = []
    footer = ""
    subtotal: Decimal | None = None
    total: Decimal | None = None
    impuestos: Decimal | None = None

    for line in lines:
        s = line.strip()
        if s.startswith("## "):
            title = s[3:].strip() or title

    for line in lines:
        s = line.strip()
        kv = match_md_kv_bullet_line(s)
        if not kv:
            continue
        key, val = kv
        lk = key.lower()
        meta_flat[lk] = val
        if "subtotal" in lk and "usd" in lk:
            v = _parse_money_value(val)
            if v is not None:
                subtotal = v
        elif "total" in lk and "usd" in lk and "subtotal" not in lk:
            v = _parse_money_value(val)
            if v is not None:
                total = v
        elif "impuesto" in lk and "usd" in lk:
            v = _parse_money_value(val)
            if v is not None:
                impuestos = v

    # Tabla de ítems
    i = 0
    while i < len(lines):
        row = lines[i].strip()
        if row.startswith("|") and "Producto" in row and "SKU" in row:
            i += 1
            while i < len(lines) and re.match(r"^\|[\s\-:|]+$", lines[i].strip()):
                i += 1
            while i < len(lines):
                data_row = lines[i].strip()
                if not data_row.startswith("|"):
                    break
                if re.match(r"^\|[\s\-:|]+$", data_row):
                    i += 1
                    continue
                parts = [p.strip() for p in data_row.split("|")[1:-1]]
                if len(parts) >= 5 and parts[0]:
                    try:
                        qty_s = parts[2].replace(",", "")
                        pu_s = parts[3].replace(",", "")
                        st_s = parts[4].replace(",", "")
                        items.append({
                            "product": parts[0],
                            "sku": parts[1] if parts[1] not in ("—", "-", "") else "",
                            "quantity": int(qty_s),
                            "unit_price": Decimal(pu_s),
                            "subtotal": Decimal(st_s),
                        })
                    except (ValueError, IndexError):
                        pass
                i += 1
            break
        i += 1

    in_notes = False
    in_adv = False
    for idx, line in enumerate(lines):
        s = line.strip()
        if s.startswith("**Notas:**"):
            in_notes = True
            in_adv = False
            notas = s.replace("**Notas:**", "").strip()
            continue
        if s.startswith("**Advertencias:**"):
            in_adv = True
            in_notes = False
            continue
        if in_notes and s:
            if s.startswith("**") or s.startswith("---"):
                in_notes = False
            elif not s.startswith("|"):
                sep = " " if notas else ""
                notas = f"{notas}{sep}{s}".strip()
        if in_adv and s.startswith("- ") and not s.startswith("---"):
            advertencias.append(s[2:].strip())
        if s.startswith("---") and idx + 1 < len(lines):
            tail = lines[idx + 1].strip()
            if tail.startswith("*") and tail.endswith("*"):
                footer = tail.strip("*").strip()

    sum_lines = sum(x["subtotal"] for x in items) if items else Decimal("0")
    if subtotal is None:
        subtotal = sum_lines
    if total is None:
        tax = impuestos or Decimal("0")
        total = subtotal + tax

    meta_out = {
        "title": title,
        "solicitante": _party_field_display(meta_flat.get("solicitante")),
        "vendedor": _party_field_display(meta_flat.get("vendedor")),
        "fecha": meta_flat.get("fecha", "").strip()
        or datetime.now().strftime("%Y-%m-%d"),
        "moneda": meta_flat.get("moneda", "").strip() or "USD",
    }

    return {
        "metadata": meta_out,
        "items": items,
        "subtotal": subtotal,
        "total": total,
        "impuestos_usd": impuestos,
        "notes": notas,
        "advertencias": advertencias,
        "footer": footer or "Precios según catálogo consultado (USD).",
        "currency": meta_out.get("moneda") or "USD",
    }


class ApprovedQuotePDF(FPDF):
    PRIMARY_COLOR = InvoicePDF.PRIMARY_COLOR
    ACCENT_COLOR = InvoicePDF.ACCENT_COLOR
    TEXT_COLOR = InvoicePDF.TEXT_COLOR
    MUTED_COLOR = InvoicePDF.MUTED_COLOR

    def header(self):
        pass

    def footer(self):
        self.set_y(-12)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(*self.MUTED_COLOR)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


def generate_approved_cotizacion_pdf(
    invoice_data: dict[str, Any],
    *,
    output_path: str | Path,
    company: CompanyProfile | None = None,
    logo_path: str | Path | None = None,
    quote_reference: str,
) -> None:
    """PDF profesional: empresa (bloque explícito), cotización y marca de aprobación."""
    company = company or CompanyProfile.from_env()
    pdf = ApprovedQuotePDF()
    pdf.add_page()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=22)

    currency = _pdf_safe(str(invoice_data.get("currency") or "USD"))
    meta = invoice_data.get("metadata") or {}

    # Franja superior
    pdf.set_fill_color(*ApprovedQuotePDF.PRIMARY_COLOR)
    pdf.rect(0, 0, 210, 36, style="F")

    lp = logo_path or os.getenv("QUOTE_COMPANY_LOGO_PATH", "").strip()
    if lp and Path(lp).is_file():
        try:
            pdf.image(str(lp), 14, 7, 22)
        except Exception:
            pass

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 18)
    pdf.set_xy(42, 10)
    pdf.cell(100, 8, "COTIZACIÓN APROBADA", align="L")
    pdf.set_font("helvetica", "", 9)
    pdf.set_xy(42, 19)
    pdf.cell(100, 5, _pdf_safe(meta.get("title", "Cotización")), align="L")

    pdf.set_xy(130, 11)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(68, 5, quote_reference, align="R")
    pdf.set_font("helvetica", "", 9)
    pdf.set_xy(130, 18)
    pdf.cell(68, 5, f"Emitido: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="R")

    pdf.set_y(42)
    pdf.set_text_color(*ApprovedQuotePDF.TEXT_COLOR)

    # Dos columnas: empresa | estado documento
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(92, 6, "Datos de la empresa emisora")
    pdf.set_xy(110, pdf.get_y())
    pdf.cell(82, 6, "Estado del documento", align="R")
    pdf.ln(8)

    pdf.set_font("helvetica", "", 9)
    x0, y0 = pdf.get_x(), pdf.get_y()

    lines_company: list[str] = []
    if company.trade_name:
        lines_company.append(_pdf_safe(company.trade_name))
    if company.legal_name:
        lines_company.append(_pdf_safe(f"Razón social: {company.legal_name}"))
    if company.tax_id:
        lines_company.append(_pdf_safe(f"NIT / ID fiscal: {company.tax_id}"))
    if company.address:
        lines_company.append(_pdf_safe(company.address))
    if company.phone:
        lines_company.append(_pdf_safe(f"Tel.: {company.phone}"))
    if company.email:
        lines_company.append(_pdf_safe(f"Email: {company.email}"))
    if company.website:
        lines_company.append(_pdf_safe(company.website))
    if not lines_company:
        lines_company.append(
            "(Configure QUOTE_COMPANY_TRADE_NAME y demás QUOTE_COMPANY_* en .env)"
        )

    pdf.set_xy(x0, y0)
    pdf.set_fill_color(*ApprovedQuotePDF.ACCENT_COLOR)
    pdf.rect(x0, y0, 88, 42, style="F")
    pdf.set_xy(x0 + 3, y0 + 3)
    for ln in lines_company:
        pdf.multi_cell(82, 5, ln)
        pdf.set_x(x0 + 3)

    pdf.set_xy(110, y0)
    pdf.set_fill_color(245, 252, 245)
    pdf.rect(110, y0, 82, 42, style="F")
    pdf.set_xy(113, y0 + 3)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(20, 110, 60)
    pdf.multi_cell(76, 6, "APROBADA - Válida para emisión al cliente")
    pdf.set_text_color(*ApprovedQuotePDF.TEXT_COLOR)
    pdf.set_font("helvetica", "", 9)
    pdf.set_xy(113, y0 + 18)
    pdf.multi_cell(76, 5, f"Referencia interna:\n{quote_reference}")
    pdf.set_xy(113, y0 + 30)
    pdf.multi_cell(76, 5, f"Moneda cotización: {currency}")

    pdf.set_y(y0 + 48)

    # Datos de la cotización (cliente / operación)
    pdf.set_fill_color(*ApprovedQuotePDF.ACCENT_COLOR)
    pdf.rect(18, pdf.get_y(), 174, 26, style="F")
    band_top = pdf.get_y()
    pdf.set_xy(22, band_top + 4)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(170, 5, "Datos de la cotización")
    pdf.ln(8)
    pdf.set_font("helvetica", "", 9)
    pdf.set_x(22)
    sol = _party_field_display(meta.get("solicitante"))
    ven = _party_field_display(meta.get("vendedor"))
    pdf.cell(85, 5, f"Solicitante: {sol}")
    pdf.cell(85, 5, f"Vendedor: {ven}", align="R")
    pdf.ln(6)
    pdf.set_x(22)
    pdf.cell(85, 5, _pdf_safe(f"Fecha cotización: {meta.get('fecha', '-')}"))
    pdf.cell(
        85,
        5,
        _pdf_safe(f"Moneda: {meta.get('moneda', currency)}"),
        align="R",
    )
    pdf.set_y(band_top + 30)

    # Tabla
    pdf.set_fill_color(*ApprovedQuotePDF.PRIMARY_COLOR)
    pdf.rect(18, pdf.get_y(), 174, 9, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_xy(20, pdf.get_y() + 2)
    pdf.cell(68, 6, "Producto")
    pdf.cell(28, 6, "SKU")
    pdf.cell(14, 6, "Cant.", align="R")
    pdf.cell(30, 6, f"P. unit. ({currency})", align="R")
    pdf.cell(28, 6, f"Subtotal ({currency})", align="R")
    pdf.set_y(pdf.get_y() + 9)
    pdf.set_text_color(*ApprovedQuotePDF.TEXT_COLOR)

    pdf.set_font("helvetica", "", 9)
    rows = invoice_data.get("items") or []
    if not rows:
        pdf.set_fill_color(252, 252, 252)
        pdf.rect(18, pdf.get_y(), 174, 12, style="F")
        pdf.set_xy(22, pdf.get_y() + 3)
        pdf.set_font("helvetica", "I", 9)
        pdf.cell(170, 6, "(Sin líneas en formato tabla; revise el texto completo del borrador.)")
        pdf.set_font("helvetica", "", 9)
        pdf.set_y(pdf.get_y() + 12)
    else:
        for i, item in enumerate(rows):
            row_h = 10
            if i % 2 == 0:
                pdf.set_fill_color(250, 250, 250)
                pdf.rect(18, pdf.get_y(), 174, row_h, style="F")
            pdf.set_xy(20, pdf.get_y() + 2)
            name = _pdf_safe(str(item.get("product", ""))[:42])
            pdf.cell(68, 6, name)
            pdf.cell(28, 6, _pdf_safe(str(item.get("sku") or "-")))
            pdf.cell(14, 6, str(item.get("quantity", "")), align="R")
            pdf.cell(30, 6, f"{item['unit_price']:.2f}", align="R")
            pdf.cell(28, 6, f"{item['subtotal']:.2f}", align="R")
            pdf.set_y(pdf.get_y() + row_h)

    pdf.set_y(pdf.get_y() + 4)
    pdf.set_font("helvetica", "", 10)
    pdf.set_x(105)
    pdf.cell(45, 7, f"Subtotal ({currency}):", align="R")
    pdf.cell(28, 7, f"{invoice_data.get('subtotal', 0):.2f}", align="R")
    pdf.ln(7)

    imp = invoice_data.get("impuestos_usd")
    if imp is not None:
        pdf.set_x(105)
        pdf.cell(45, 7, f"Impuestos ({currency}):", align="R")
        pdf.cell(28, 7, f"{float(imp):.2f}", align="R")
        pdf.ln(7)

    pdf.set_fill_color(*ApprovedQuotePDF.PRIMARY_COLOR)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_x(102)
    pdf.cell(48, 10, f"Total ({currency})", align="R")
    pdf.cell(32, 10, f"{invoice_data.get('total', 0):.2f}", align="R")
    pdf.ln(12)
    pdf.set_text_color(*ApprovedQuotePDF.TEXT_COLOR)

    notes = _pdf_safe((invoice_data.get("notes") or "").strip())
    if notes:
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(0, 6, "Notas")
        pdf.ln(5)
        pdf.set_font("helvetica", "", 9)
        pdf.multi_cell(174, 5, notes)
        pdf.ln(2)

    adv = invoice_data.get("advertencias") or []
    if adv:
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(0, 6, "Advertencias")
        pdf.ln(5)
        pdf.set_font("helvetica", "", 9)
        for a in adv:
            pdf.multi_cell(174, 5, _pdf_safe(f"- {a}"))
        pdf.ln(2)

    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(*ApprovedQuotePDF.MUTED_COLOR)
    pdf.multi_cell(174, 4, _pdf_safe(invoice_data.get("footer", "")))
    pdf.set_text_color(*ApprovedQuotePDF.TEXT_COLOR)
    pdf.ln(4)
    pdf.set_font("helvetica", "B", 8)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        174,
        4,
        "Este PDF se generó automáticamente tras la aprobación del vendedor en el flujo interno.",
    )

    pdf.output(str(output_path))


def write_pdf_on_quote_approval(markdown_text: str) -> str | None:
    """
    Punto de entrada para el supervisor al aprobar la cotización.
    Devuelve la ruta absoluta del PDF o None si no hay contenido.
    """
    md = (markdown_text or "").strip()
    if not md:
        return None

    custom_dir = os.getenv("QUOTE_PDF_OUTPUT_DIR", "").strip()
    if custom_dir:
        root = Path(custom_dir).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parent / "approved_quotes"
    root.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    quote_ref = f"COT-{ts}-{suffix}"
    out_path = root / f"cotizacion_aprobada_{ts}_{suffix}.pdf"

    data = parse_quote_agent_markdown(md)
    logo = os.getenv("QUOTE_COMPANY_LOGO_PATH", "").strip() or None

    generate_approved_cotizacion_pdf(
        data,
        output_path=out_path,
        company=CompanyProfile.from_env(),
        logo_path=logo,
        quote_reference=quote_ref,
    )
    return str(out_path.resolve())


# Example usage
if __name__ == "__main__":
    md_text = """## Cotización

- **Solicitante:** Alejandro Estrada
- **Vendedor:** Camila Ruiz
- **Fecha:** 2024-09-16
- **Moneda:** USD

| Producto | SKU | Cant. | P. unit. (USD) | Subtotal (USD) |
|----------|-----|------:|---------------:|---------------:|
| iPhone 17 256GB | IPHONE-17-256 | 3 | 829.00 | 2,487.00 |
| AirPods Pro 3 | AIRPODS-PRO-3 | 1 | 249.00 | 249.00 |

- **Subtotal (USD):** 2,736.00
- **Total (USD):** 2,736.00

**Notas:** El cliente solicitó 3 iPhone 17 de 256 GB y 1 AirPods Pro 3. Los productos más cercanos en el catálogo son el iPhone 17 256GB con un precio de $829.00 y el iPhone 17 Pro 256GB con un precio de $1199.00. Los AirPods Pro 3 tienen un precio de $249.00.

---
*Precios según catálogo consultado (USD).*
"""

    data = parse_markdown_invoice(md_text)
    data["invoice_number"] = "2024-001"
    data["currency"] = "USD"

    generate_invoice_pdf(data, "cotizacion.pdf")