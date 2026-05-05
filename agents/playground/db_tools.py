"""
Herramientas deterministas para el agente ReAct de base de datos.

- get_database_schema: lee INFORMATION_SCHEMA y devuelve un texto tipo CREATE TABLE
  (es solo descripción; no ejecuta DDL en la base).
- execute_readonly_query: valida y ejecuta un único SELECT contra Postgres (Supabase).

No hay LLM dentro de estas funciones: solo I/O y reglas de seguridad.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlparse

logger = logging.getLogger(__name__)

# Tablas que existen en prisma/schema.prisma (nombres físicos en Postgres).
ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "employees",
        "customers",
        "products",
        "invoices",
        "invoice_items",
    }
)

# Comandos que nunca debe ejecutar el agente a través de esta tool.
_FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "COPY",
        "CALL",
        "EXECUTE",
        "PREPARE",
    }
)

DEFAULT_ROW_LIMIT = 100
STATEMENT_TIMEOUT_MS = 8000


def _get_direct_url() -> str:
    """URL de conexión Postgres (variable DIRECT_URL del .env, usada por Prisma)."""
    url = os.getenv("DIRECT_URL", "").strip()
    if not url:
        raise ValueError(
            "Falta DIRECT_URL en el entorno. "
            "Configúrela en .env (cadena postgresql://... de Supabase)."
        )
    return url


def get_database_schema(tables_arg: str) -> str:
    """
    Devuelve un texto legible para el LLM con la forma de cada tabla permitida.

    ``tables_arg``:
      - Cadena vacía o \"[]\" → todas las tablas permitidas.
      - \"invoices\" → una tabla.
      - \"invoices,customers\" → varias, separadas por coma (sin espacios obligatorios).

    El formato es pseudo-DDL (CREATE TABLE ...) para que el modelo reconozca columnas y tipos.
    """
    raw = (tables_arg or "").strip()
    if not raw or raw in ("[]", "all", "ALL"):
        tables: list[str] = sorted(ALLOWED_TABLES)
    else:
        tables = [t.strip().lower() for t in raw.split(",") if t.strip()]

    unknown = set(tables) - ALLOWED_TABLES
    if unknown:
        return (
            f"Error: tabla(s) no permitida(s) para inspección: {sorted(unknown)}. "
            f"Solo se permiten: {sorted(ALLOWED_TABLES)}."
        )

    import psycopg2
    from psycopg2.extras import RealDictCursor

    sql = """
        SELECT table_name, column_name, data_type,
               character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ANY(%s)
        ORDER BY table_name, ordinal_position;
    """

    conn = psycopg2.connect(_get_direct_url())
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (tables,))
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return f"No se encontraron columnas para las tablas solicitadas: {tables}."

    # Agrupar columnas por tabla
    by_table: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_table[r["table_name"]].append(r)

    lines: list[str] = []
    lines.append(
        "# Esquema (referencia; NO es un script a ejecutar — solo descripción de columnas)\n"
    )

    for tname in sorted(by_table.keys()):
        lines.append(f"-- Tabla: {tname}")
        lines.append(f"CREATE TABLE {tname} (")
        col_lines: list[str] = []
        for col in by_table[tname]:
            dt = col["data_type"] or "unknown"
            if col["character_maximum_length"]:
                dt = f"{dt}({col['character_maximum_length']})"
            null = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
            col_lines.append(f"    {col['column_name']} {dt} {null}")
        lines.append(",\n".join(col_lines))
        lines.append(");\n")

    return "\n".join(lines)


def _is_readonly_select(text: str) -> bool:
    """
    Comprueba que sea una consulta de lectura típica.
    Acepta SELECT ... o WITH ... (CTE) que suele terminar en SELECT.
    """
    collapsed = sqlparse.format(text, strip_comments=True).strip()
    if not collapsed:
        return False
    first = collapsed.split()[0].upper()
    return first in ("SELECT", "WITH")


def _extract_cte_names(sql: str) -> set[str]:
    """Nombres de CTE en WITH ... AS (...), útiles para ignorar alias en FROM."""
    names: set[str] = set()
    if not re.search(r"(?is)^\s*WITH\b", sql):
        return names
    m0 = re.search(r"(?is)^\s*WITH\s+([a-z_][a-z0-9_]*)\s+AS\s*\(", sql)
    if m0:
        names.add(m0.group(1).lower())
    for m in re.finditer(r"(?is)\)\s*,\s*([a-z_][a-z0-9_]*)\s+AS\s*\(", sql):
        names.add(m.group(1).lower())
    return names


def _extract_tables_simple(sql: str) -> set[str]:
    """
    Lista nombres de tabla tras FROM y JOIN (solo identificadores simples).
    No cubre todos los casos de SQL avanzado; refuerza la lista blanca.
    """
    # Normalizar espacios
    s = sql.strip()
    found: set[str] = set()
    for m in re.finditer(
        r"(?is)\b(?:FROM|JOIN)\s+(?:public\.)?([a-z_][a-z0-9_]*)\b",
        s,
    ):
        found.add(m.group(1).lower())
    return found


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """
    Valida que el texto sea un único SELECT seguro para las tablas permitidas.

    Devuelve (True, sql_listo) o (False, mensaje_error).
    """
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        return False, "La consulta SQL está vacía."

    # Una sola sentencia: no permitir ; en medio (evita DROP; SELECT...)
    if ";" in text:
        return False, "Usa una sola sentencia sin caracteres ';' en el medio."

    upper = f" {text.upper()} "
    for bad in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{bad}\b", upper):
            return False, f"No está permitido usar el comando SQL '{bad}'. Solo SELECT."

    if not _is_readonly_select(text):
        return False, "Solo se permiten consultas que empiecen con SELECT o WITH (lectura)."

    tables_used = _extract_tables_simple(text)
    if not tables_used:
        return False, "No se detectaron tablas tras FROM/JOIN (¿falta FROM?)."

    bad_tables = tables_used - ALLOWED_TABLES - _extract_cte_names(text)
    if bad_tables:
        return False, (
            f"Tablas no permitidas: {sorted(bad_tables)}. "
            f"Solo: {sorted(ALLOWED_TABLES)}."
        )

    if re.search(r"(?is)\blimit\s+\d+", text):
        final_sql = text
    else:
        final_sql = f"{text} LIMIT {DEFAULT_ROW_LIMIT}"

    return True, final_sql


def _json_safe_sql_value(v: Any) -> Any:
    """Convierte valores de Postgres/psycopg2 a tipos que json.dumps serialice sin error."""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    if isinstance(v, dict):
        out: dict[str, Any] = {}
        for k, x in v.items():
            sk = k if isinstance(k, str) else str(k)
            bump = 0
            base = sk
            while sk in out:
                bump += 1
                sk = f"{base}__{bump}"
            out[sk] = _json_safe_sql_value(x)
        return out
    if isinstance(v, (list, tuple)):
        return [_json_safe_sql_value(x) for x in v]
    if isinstance(v, (bytes, bytearray, memoryview)):
        try:
            b = bytes(v)
            return b.decode("utf-8", errors="replace")
        except Exception:
            return str(v)
    return str(v)


def _sql_row_to_json_dict(r: dict[Any, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in dict(r).items():
        sk = k if isinstance(k, str) else str(k)
        bump = 0
        base = sk
        while sk in out:
            bump += 1
            sk = f"{base}__{bump}"
        out[sk] = _json_safe_sql_value(v)
    return out


def execute_readonly_query(sql: str) -> str:
    """
    Ejecuta un SELECT validado y devuelve filas en JSON (texto).

    El argumento ``sql`` debe ser un único SELECT; se aplica lista blanca y LIMIT.
    """
    ok, result = validate_readonly_sql(sql)
    if not ok:
        return f"Error de validación: {result}"

    final_sql = result

    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(_get_direct_url())
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
            cur.execute(final_sql)
            rows = cur.fetchmany(DEFAULT_ROW_LIMIT + 1)
    except Exception as e:
        logger.warning("execute_readonly_query falló: %s", e)
        return f"Error de base de datos (la query no se ejecutó o falló): {e}"
    finally:
        conn.close()

    if len(rows) > DEFAULT_ROW_LIMIT:
        rows = rows[:DEFAULT_ROW_LIMIT]
        note = f"\n(Nota: resultados truncados a {DEFAULT_ROW_LIMIT} filas.)"
    else:
        note = ""

    # Serializar: anida dict/list (p. ej. jsonb), Decimal, fechas, UUID; claves siempre str.
    serializable = [_sql_row_to_json_dict(dict(r)) for r in rows]

    payload = json.dumps(serializable, ensure_ascii=False, indent=2)
    return f"Filas devueltas ({len(serializable)}):\n{payload}{note}"
