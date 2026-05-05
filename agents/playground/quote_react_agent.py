"""
Agente ReAct para cotizaciones: consulta precios en BD (solo lectura) y arma un documento
estructurado (Pydantic). No modifica db_react_agent.py; reutiliza parse_db_action y execute_db_tool.

Fase 1: mismo patrón Thought → Action → Observation que DBReactAgent.
Fase 2: LLM genera JSON validado contra modelos Pydantic (precios en USD según catálogo).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from difflib import SequenceMatcher
from decimal import Decimal
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI
from pydantic import BaseModel, Field, model_validator

from agents.playground.db_react_agent import (
    execute_db_tool,
    parse_db_action,
    _print_trace_step,
    _resolve_verbose,
)

load_dotenv()

logger = logging.getLogger(__name__)

_GROQ_BASE = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


QUOTE_REACT_SYSTEM_PROMPT = """\
Eres un experto en cotizaciones para un reseller Apple. Tu trabajo es armar una cotización \
basándote SOLO en datos que obtengas de la base (tabla products: name, sku, category, unit_price).

IMPORTANTE: Los precios en catálogo (`unit_price`) están en DÓLARES (USD). No conviertas moneda \
ni inventes precios.

Herramientas — formato exacto por paso:

1) get_database_schema[LISTA]
   - Vacío get_database_schema[] para todas las tablas permitidas, o get_database_schema[products].

2) execute_readonly_query[SQL]
   - Solo SELECT de lectura. Sin punto y coma final.

3) Finish[respuesta]
   - Texto en español (NO JSON aquí). Resume para la siguiente fase:
     - Productos solicitados por el cliente y cantidades.
     - Por cada producto: nombre exacto en BD, sku, unit_price en USD visto en observaciones, \
subtotal línea (cantidad × unit_price).
     - Si un producto no aparece en BD, dilo claramente, salvo que el Observation traiga \
«Sugerencia por similitud»: en ese caso usa ese ítem como propuesta (el usuario puede ajustar \
la cotización después).
     - Si el usuario menciona vendedor o solicitante y hay datos en observaciones, inclúyelos.
     - Total estimado en USD si todas las líneas tienen precio.

Buen flujo: esquema products si hace falta → SELECT que encuentre productos por nombre o sku \
(ILIKE '%...%' con cuidado) → Finish.

Si una consulta a products devuelve 0 filas y hay «Sugerencia por similitud», cotiza con ese \
producto; en Finish puedes decir que es la coincidencia más cercana del catálogo (revisable).

Límites:
- Máximo {max_steps} pasos.
- Cada respuesta SOLO dos líneas, sin markdown:
Thought N: ...
Action N: ...

Tras cada Action recibirás:
Observation N: (texto de la herramienta)
"""


class CotizacionLineItem(BaseModel):
    nombre: str = Field(description="Nombre del producto como en catálogo.")
    sku: str = Field(default="", description="SKU en BD si se conoce.")
    cantidad: int = Field(ge=1)
    precio_unitario_usd: float = Field(ge=0, description="Precio unitario en USD.")
    subtotal_linea_usd: float = Field(ge=0, description="cantidad × precio_unitario.")


class Cotizacion(BaseModel):
    solicitante: str = Field(default="consumidor")
    vendedor_nombre: str = Field(default="", description="Nombre del empleado si aplica.")
    vendedor_id: str = Field(default="", description="UUID empleado si se conoce.")
    moneda: str = Field(default="USD")
    fecha_cotizacion: str = Field(
        default_factory=lambda: date.today().isoformat(),
        description="YYYY-MM-DD",
    )
    items: list[CotizacionLineItem] = Field(default_factory=list)
    subtotal_usd: float = Field(ge=0, default=0)
    impuestos_usd: float | None = Field(default=None)
    total_usd: float = Field(ge=0, default=0)
    advertencias: list[str] = Field(default_factory=list)
    notas: str = Field(default="", description="Notas breves al cliente.")

    @model_validator(mode="after")
    def totals_vs_lines(self) -> Cotizacion:
        if not self.items:
            return self
        s = round(sum(x.subtotal_linea_usd for x in self.items), 2)
        st = round(self.subtotal_usd, 2)
        if abs(s - st) > 0.05:
            self.advertencias.append(
                f"Ajuste numérico: subtotal declarado {st} vs suma líneas {s}; se prioriza suma líneas."
            )
            self.subtotal_usd = s
        tax = self.impuestos_usd or 0.0
        tot = round(self.subtotal_usd + tax, 2)
        if abs(tot - round(self.total_usd, 2)) > 0.05:
            self.total_usd = tot
        return self


def _parse_cotizacion_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No se encontró JSON de cotización.")
    blob = text[start : end + 1]
    data = json.loads(blob)
    if not isinstance(data, dict):
        raise ValueError("La cotización JSON debe ser un objeto.")
    return data


def _normalize_payload_for_cotizacion(data: dict[str, Any]) -> dict[str, Any]:
    """Mapea aliases del modelo a los nombres del modelo Pydantic."""
    out = dict(data)
    items_raw = out.get("items") or out.get("lineas") or []
    norm_items: list[dict[str, Any]] = []
    if isinstance(items_raw, list):
        for it in items_raw:
            if not isinstance(it, dict):
                continue
            norm_items.append({
                "nombre": str(it.get("nombre") or it.get("name") or ""),
                "sku": str(it.get("sku") or ""),
                "cantidad": int(it.get("cantidad") or it.get("quantity") or 1),
                "precio_unitario_usd": float(
                    it.get("precio_unitario_usd")
                    or it.get("precio_unitario")
                    or it.get("unit_price")
                    or 0
                ),
                "subtotal_linea_usd": float(
                    it.get("subtotal_linea_usd")
                    or it.get("subtotal_linea")
                    or it.get("line_total")
                    or 0
                ),
            })
    out["items"] = norm_items
    return out


def _get_direct_url() -> str:
    url = os.getenv("DIRECT_URL", "").strip()
    if not url:
        raise ValueError(
            "Falta DIRECT_URL en el entorno (necesaria para sugerencias por similitud)."
        )
    return url


def _load_product_catalog_from_db() -> list[dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(_get_direct_url())
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT name, sku, unit_price, category FROM products ORDER BY name"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        up = d.get("unit_price")
        if isinstance(up, Decimal):
            d["unit_price"] = float(up)
        elif up is not None and not isinstance(up, (int, float)):
            d["unit_price"] = float(up)
        out.append(d)
    return out


def _token_jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _similarity_pair(needle: str, candidate: str) -> float:
    if not needle or not candidate:
        return 0.0
    n, c = needle.lower(), candidate.lower()
    seq = SequenceMatcher(None, n, c).ratio()
    jac = _token_jaccard(needle, candidate)
    bonus = 0.12 if n in c else 0.0
    return max(seq, jac) + bonus


def _best_product_row(
    needle: str, catalog: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float]:
    best_row: dict[str, Any] | None = None
    best_score = 0.0
    for r in catalog:
        name = str(r.get("name") or "")
        sku = str(r.get("sku") or "")
        cat = str(r.get("category") or "")
        combined = f"{name} {sku} {cat}"
        s = max(
            _similarity_pair(needle, name),
            _similarity_pair(needle, sku) * 0.92,
            _similarity_pair(needle, combined),
        )
        if s > best_score:
            best_score = s
            best_row = r
    return best_row, best_score


def _extract_search_needles_from_sql(sql: str) -> list[str]:
    text = sql or ""
    needles: list[str] = []
    for m in re.finditer(r"(?is)ILIKE\s+'%([^']*)%'", text):
        s = (m.group(1) or "").strip()
        if len(s) >= 2:
            needles.append(s)
    for m in re.finditer(r"(?is)\bLIKE\s+'%([^']*)%'", text):
        s = (m.group(1) or "").strip()
        if len(s) >= 2:
            needles.append(s)
    for m in re.finditer(
        r"(?is)(?:\bname\b|\bsku\b|\bcategory\b)\s*=\s*'([^']+)'",
        text,
    ):
        s = (m.group(1) or "").strip()
        if len(s) >= 2:
            needles.append(s)
    seen: set[str] = set()
    out: list[str] = []
    for n in needles:
        k = n.lower()
        if k not in seen:
            seen.add(k)
            out.append(n)
    return out


def _parse_observation_row_count(observation: str) -> int | None:
    m = re.search(r"Filas devueltas \((\d+)\)\s*:", observation or "")
    if m:
        return int(m.group(1))
    return None


def _maybe_append_similarity_observation(
    sql: str,
    observation: str,
    catalog: list[dict[str, Any]],
) -> str:
    if "products" not in (sql or "").lower():
        return observation
    n = _parse_observation_row_count(observation)
    if n is None or n > 0:
        return observation
    needles = _extract_search_needles_from_sql(sql)
    needle = " ".join(needles).strip()
    if len(needle) < 2:
        return observation
    row, score = _best_product_row(needle, catalog)
    if not row:
        return observation
    name = str(row.get("name") or "")
    sku = str(row.get("sku") or "")
    price = row.get("unit_price")
    price_f = float(price) if price is not None else 0.0
    cat = row.get("category")
    hint = (
        f"\n\nSugerencia por similitud (0 filas en la consulta; término «{needle}»):\n"
        f"Propuesta del catálogo más parecida: name={name!r}, sku={sku!r}, "
        f"unit_price={price_f} USD, category={cat!r}. "
        f"Similitud (orientativa): {score:.2f}. "
        "Úsala en la cotización si sirve; el resultado se puede corregir a mano después."
    )
    return observation + hint


_SIMILARITY_MIN_AUTOFILL = 0.28


def enrich_cotizacion_similarity_lines(
    cot: Cotizacion, catalog: list[dict[str, Any]]
) -> Cotizacion:
    """Completa líneas sin precio eligiendo el producto del catálogo más similar al nombre."""
    items_out: list[dict[str, Any]] = []
    extra_warn: list[str] = []
    for it in cot.items:
        d = it.model_dump()
        pu = float(d.get("precio_unitario_usd") or 0)
        if pu > 0:
            items_out.append(d)
            continue
        needle = str(d.get("nombre") or "").strip()
        if len(needle) < 2:
            items_out.append(d)
            continue
        row, score = _best_product_row(needle, catalog)
        if not row or score < _SIMILARITY_MIN_AUTOFILL:
            items_out.append(d)
            continue
        up = row.get("unit_price")
        unit = float(up) if up is not None else 0.0
        qty = int(d.get("cantidad") or 1)
        d["nombre"] = str(row.get("name") or needle)
        d["sku"] = str(row.get("sku") or "")
        d["precio_unitario_usd"] = unit
        d["subtotal_linea_usd"] = round(qty * unit, 2)
        items_out.append(d)
        extra_warn.append(
            f"Línea «{needle}» sin precio en el resumen; se propuso el ítem más parecido del "
            f"catálogo «{row.get('name')}» (similitud {score:.2f}). Puede editar la cotización si "
            f"prefiere otro producto."
        )
    payload = cot.model_dump()
    payload["items"] = items_out
    payload["advertencias"] = list(cot.advertencias) + extra_warn
    return Cotizacion.model_validate(payload)


def _catalog_by_sku_casefold(catalog: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in catalog:
        sk = str(r.get("sku") or "").strip()
        if sk:
            out[sk.casefold()] = r
    return out


def canonicalize_cotizacion_line_items(
    cot: Cotizacion, catalog: list[dict[str, Any]]
) -> Cotizacion:
    """
    Columna Producto = nombre exacto en BD. Por SKU válido se alinea nombre y precios;
    si el SKU no está en catálogo, se usa el ítem de mayor similitud y se sustituye nombre/sku/precio.
    """
    by_sku = _catalog_by_sku_casefold(catalog)
    items_out: list[dict[str, Any]] = []
    extra_warn: list[str] = []
    for it in cot.items:
        d = it.model_dump()
        sku = str(d.get("sku") or "").strip()
        name = str(d.get("nombre") or "").strip()
        qty = int(d.get("cantidad") or 1)

        row = by_sku.get(sku.casefold()) if sku else None
        if row:
            dbn = str(row.get("name") or "")
            if dbn:
                d["nombre"] = dbn
            d["sku"] = str(row.get("sku") or sku)
            up = float(row.get("unit_price") or 0)
            d["precio_unitario_usd"] = up
            d["subtotal_linea_usd"] = round(qty * up, 2)
            items_out.append(d)
            continue

        if len(name) < 2:
            items_out.append(d)
            continue

        brow, score = _best_product_row(name, catalog)
        if not brow or score < _SIMILARITY_MIN_AUTOFILL:
            items_out.append(d)
            continue

        dbn = str(brow.get("name") or "")
        if not dbn:
            items_out.append(d)
            continue

        matched_sku = str(brow.get("sku") or "")
        up = float(brow.get("unit_price") or 0)
        renamed = name.casefold() != dbn.casefold()
        if renamed:
            extra_warn.append(
                f"La línea «{name}» (SKU en borrador no hallado en catálogo) se mostró como "
                f"«{dbn}» — nombre y datos según ese ítem en BD (similitud {score:.2f})."
            )
        d["nombre"] = dbn
        if matched_sku:
            d["sku"] = matched_sku
        d["precio_unitario_usd"] = up
        d["subtotal_linea_usd"] = round(qty * up, 2)
        items_out.append(d)

    payload = cot.model_dump()
    payload["items"] = items_out
    payload["advertencias"] = list(cot.advertencias) + extra_warn
    return Cotizacion.model_validate(payload)


class QuoteReactAgent:
    """Bucle ReAct copiado del DBReactAgent (sin modificar db_react_agent.py)."""

    def __init__(
        self,
        model: str | None = None,
        max_steps: int = 24,
        timeout: float = 90.0,
    ):
        self.model = model or _DEFAULT_MODEL
        self.max_steps = max_steps
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY no está definida.")
        self.client = OpenAI(
            base_url=_GROQ_BASE,
            api_key=api_key,
            timeout=timeout,
        )
        self._product_catalog: list[dict[str, Any]] | None = None

    def _get_catalog(self) -> list[dict[str, Any]]:
        if self._product_catalog is None:
            self._product_catalog = _load_product_catalog_from_db()
        return self._product_catalog

    def product_catalog_if_loaded(self) -> list[dict[str, Any]] | None:
        """Catálogo en memoria si ya se cargó durante el bucle ReAct; si no, None."""
        return self._product_catalog

    def run(self, question: str, verbose: bool | None = None) -> dict:
        verbose = _resolve_verbose(verbose)
        trajectory = f"Question: {question}\n"
        system = QUOTE_REACT_SYSTEM_PROMPT.format(max_steps=self.max_steps)
        steps: list[dict] = []

        if verbose:
            print()
            print("═" * 60)
            print(" Quote ReAct · cotización (paso a paso)")
            print("═" * 60)
            for line in question.strip().splitlines() or [""]:
                print(f"  {line}")
            print("═" * 60 + "\n")

        for step in range(1, self.max_steps + 1):
            if self._detect_loop(trajectory):
                trajectory += (
                    f"Thought {step}: Repetí la misma acción; debo cambiar de estrategia o usar Finish.\n"
                )
                if verbose:
                    print(f"[aviso] Posible bucle detectado en el paso {step}\n")

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": trajectory},
                    ],
                    temperature=0,
                    max_tokens=2048,
                )
                raw = (response.choices[0].message.content or "").strip()
            except Exception as e:
                logger.error("Quote ReAct paso %s: %s", step, e)
                if verbose:
                    print(f"── Paso {step} ── ERROR LLM: {e}\n")
                steps.append({"step": step, "error": str(e)})
                return {
                    "answer": None,
                    "steps": steps,
                    "trajectory": trajectory,
                    "error": str(e),
                }

            thought, action_line = self._parse_react_output(raw, step)
            call = parse_db_action(action_line)

            if call.tool == "Finish":
                if verbose:
                    _print_trace_step(
                        step, thought, call, observation=None, raw_action_line=action_line
                    )
                trajectory += f"Thought {step}: {thought}\nAction {step}: {action_line}\n"
                steps.append(
                    {
                        "step": step,
                        "thought": thought,
                        "action": action_line,
                        "finish": call.argument,
                    }
                )
                return {
                    "answer": call.argument,
                    "steps": steps,
                    "trajectory": trajectory,
                }

            result = execute_db_tool(call)
            observation = result.output
            if call.tool == "execute_readonly_query":
                try:
                    observation = _maybe_append_similarity_observation(
                        call.argument,
                        observation,
                        self._get_catalog(),
                    )
                except Exception as e:
                    logger.warning("Sugerencia por similitud no aplicada: %s", e)

            if verbose:
                _print_trace_step(
                    step, thought, call, observation, raw_action_line=action_line
                )

            steps.append(
                {
                    "step": step,
                    "thought": thought,
                    "action": action_line,
                    "observation_preview": observation[:300],
                }
            )
            trajectory += (
                f"Thought {step}: {thought}\n"
                f"Action {step}: {action_line}\n"
                f"Observation {step}: {observation}\n"
            )

        logger.warning("Quote ReAct: max_steps=%s sin Finish", self.max_steps)
        return {
            "answer": None,
            "steps": steps,
            "trajectory": trajectory,
        }

    @staticmethod
    def _detect_loop(trajectory: str, window: int = 3) -> bool:
        actions = re.findall(r"Action\s+\d+:\s*(.+)", trajectory, flags=re.MULTILINE)
        if len(actions) < window:
            return False
        return len(set(a.strip() for a in actions[-window:])) == 1

    @staticmethod
    def _clean_markdown(text: str) -> str:
        t = re.sub(r"\*{1,2}", "", text).strip()
        t = re.sub(r"(?m)^#+\s*", "", t)
        return t

    def _parse_react_output(self, raw: str, step: int) -> tuple[str, str]:
        cleaned = self._clean_markdown(raw)
        if not cleaned:
            return "Respuesta vacía del modelo.", ""

        thought_pat = r"(?:thought|pensamiento|razonamiento)"
        action_pat = r"(?:action|acción|accion)"

        def extract_tool_line(blob: str) -> str | None:
            m = re.search(
                r"(?is)\b(execute_readonly_query|get_database_schema|Finish|finish)\s*\[",
                blob,
            )
            if not m:
                return None
            frag = blob[m.start() :]
            if "]" not in frag:
                return None
            return frag[: frag.rindex("]") + 1].strip()

        def flex_thought(text: str) -> str:
            m = re.search(
                rf"(?is){thought_pat}\s*\d*\s*:\s*(.+?)(?={action_pat}\s*\d*\s*:|$)",
                text,
                re.DOTALL,
            )
            if m:
                return m.group(1).strip()
            return "Sin razonamiento explícito."

        def strict_thought(text: str, st: int) -> str | None:
            m = re.search(
                rf"(?is){thought_pat}\s*{st}\s*:\s*(.+?)(?={action_pat}\s*{st}\s*:|$)",
                text,
                re.DOTALL,
            )
            if m:
                return m.group(1).strip()
            return None

        am = re.search(rf"(?is){action_pat}\s*{step}\s*:\s*(.*)", cleaned, re.DOTALL)
        if am:
            blob = am.group(1).strip()
            tool = extract_tool_line(blob)
            if tool:
                th = strict_thought(cleaned, step) or flex_thought(cleaned)
                return th, tool
            head = blob.split("\n")[0].strip()
            if head:
                th = strict_thought(cleaned, step) or flex_thought(cleaned)
                return th, head

        am = re.search(rf"(?is){action_pat}\s*\d*\s*:\s*(.*)", cleaned, re.DOTALL)
        if am:
            blob = am.group(1).strip()
            tool = extract_tool_line(blob)
            if tool:
                return flex_thought(cleaned), tool
            head = blob.split("\n")[0].strip()
            if head:
                return flex_thought(cleaned), head

        tool = extract_tool_line(cleaned)
        if tool:
            return flex_thought(cleaned), tool

        for line in reversed(cleaned.split("\n")):
            line = line.strip()
            if any(
                line.startswith(p)
                for p in (
                    "get_database_schema",
                    "execute_readonly_query",
                    "Finish",
                    "finish",
                )
            ):
                return flex_thought(cleaned), line

        return flex_thought(cleaned), ""


_STRUCT_SYSTEM = """\
Eres un generador de cotizaciones estructuradas para un reseller Apple.

Entrada: mensaje original del cliente, resumen del agente que consultó la BD, y un fragmento \
del historial de observaciones SQL (solo para referencia).

Reglas:
- Montos en USD. precio_unitario_usd y subtotal_linea_usd deben venir del resumen u observaciones; \
si había «Sugerencia por similitud», esos valores cuentan como datos de catálogo (propuesta revisable). \
Si falta precio sin sugerencia, advertencias y omite o cantidad coherente.
- subtotal_linea_usd DEBE ser cantidad × precio_unitario_usd (redondeo 2 decimales).
- solicitante: si no hay nombre en el texto, usa "consumidor".
- vendedor_nombre: si no hay dato, cadena vacía.
- fecha_cotizacion: fecha en que se emite esta cotización (hoy, calendario local). Formato YYYY-MM-DD. \
No uses fechas del resumen u observaciones si son del pasado u otra fuente.
- items[].nombre: cuando el resumen u observaciones traigan productos de la tabla products, copia el \
valor exacto del campo name tal como en BD (no uses solo el lenguaje del cliente).

Responde ÚNICAMENTE con un objeto JSON válido (sin markdown). Esquema:
{
  "solicitante": "...",
  "vendedor_nombre": "",
  "vendedor_id": "",
  "moneda": "USD",
  "fecha_cotizacion": "YYYY-MM-DD",
  "items": [
    {
      "nombre": "...",
      "sku": "",
      "cantidad": 1,
      "precio_unitario_usd": 0.0,
      "subtotal_linea_usd": 0.0
    }
  ],
  "subtotal_usd": 0.0,
  "impuestos_usd": null,
  "total_usd": 0.0,
  "advertencias": [],
  "notas": ""
}
"""


def _structure_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=_DEFAULT_MODEL,
        api_key=os.getenv("GROQ_API_KEY"),
        base_url=_GROQ_BASE,
        temperature=0,
        max_tokens=4096,
    )


def build_cotizacion_from_react(
    user_query: str,
    react_answer: str,
    trajectory: str,
) -> Cotizacion:
    traj_clip = trajectory[-14000:] if len(trajectory) > 14000 else trajectory
    llm = _structure_llm()
    reply = llm.invoke([
        SystemMessage(content=_STRUCT_SYSTEM),
        HumanMessage(
            content=json.dumps({
                "mensaje_cliente": user_query,
                "resumen_agente_bd": react_answer,
                "fragmento_trajectory": traj_clip,
            }, ensure_ascii=False),
        ),
    ])
    raw = reply.content if isinstance(reply.content, str) else str(reply.content or "")
    payload = _normalize_payload_for_cotizacion(_parse_cotizacion_json(raw))
    return Cotizacion.model_validate(payload)


def format_cotizacion_markdown(c: Cotizacion) -> str:
    lines = [
        "## Cotización",
        "",
        f"- **Solicitante:** {c.solicitante}",
        f"- **Vendedor:** {c.vendedor_nombre or '—'}",
        f"- **Fecha:** {c.fecha_cotizacion}",
        f"- **Moneda:** {c.moneda}",
        "",
        "| Producto | SKU | Cant. | P. unit. (USD) | Subtotal (USD) |",
        "|----------|-----|------:|---------------:|---------------:|",
    ]
    for it in c.items:
        lines.append(
            f"| {it.nombre} | {it.sku or '—'} | {it.cantidad} | "
            f"{it.precio_unitario_usd:,.2f} | {it.subtotal_linea_usd:,.2f} |"
        )
    lines.extend([
        "",
        f"- **Subtotal (USD):** {c.subtotal_usd:,.2f}",
    ])
    if c.impuestos_usd is not None:
        lines.append(f"- **Impuestos (USD):** {c.impuestos_usd:,.2f}")
    lines.append(f"- **Total (USD):** {c.total_usd:,.2f}")
    if c.notas.strip():
        lines.extend(["", f"**Notas:** {c.notas.strip()}"])
    if c.advertencias:
        lines.extend(["", "**Advertencias:**"] + [f"- {a}" for a in c.advertencias])
    lines.extend(["", "---", "*Precios según catálogo consultado (USD).*"])
    return "\n".join(lines)


def run_quote_react_agent(
    question: str,
    *,
    max_steps: int = 24,
    verbose: bool | None = None,
    model: str | None = None,
) -> str:
    """
    Ejecuta cotización: ReAct BD + estructura Pydantic. Devuelve Markdown para el usuario.
    """
    agent = QuoteReactAgent(model=model, max_steps=max_steps)
    result = agent.run(question, verbose=verbose)
    ans = result.get("answer")
    traj = result.get("trajectory") or ""
    err = result.get("error")

    if err and not ans:
        return (
            f"No se pudo consultar para la cotización (error técnico). Detalle: {err}\n"
            "Intente de nuevo o contacte un asesor."
        )
    if not ans:
        return (
            "No se completó la cotización en el número de pasos permitido. "
            "Pruebe acotando productos o revise la conexión a la base de datos."
        )

    try:
        cot = build_cotizacion_from_react(question, ans, traj)
        cat = agent.product_catalog_if_loaded()
        if cat is None:
            try:
                cat = _load_product_catalog_from_db()
            except Exception:
                logger.warning(
                    "Refinamiento por similitud sobre Cotizacion omitido (sin catálogo).",
                    exc_info=True,
                )
        if cat:
            cot = enrich_cotizacion_similarity_lines(cot, cat)
            cot = canonicalize_cotizacion_line_items(cot, cat)
        payload_fm = cot.model_dump()
        payload_fm["fecha_cotizacion"] = date.today().isoformat()
        cot = Cotizacion.model_validate(payload_fm)
        return format_cotizacion_markdown(cot)
    except Exception:
        logger.exception("Fallo al estructurar cotización; se devuelve resumen ReAct")
        return (
            "## Cotización (borrador sin validación completa)\n\n"
            f"{ans}\n\n"
            "_No se pudo convertir a formato estructurado automático; revise datos en sistema._"
        )
