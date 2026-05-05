"""
Agente ReAct para consultas a la base de datos (Postgres / Supabase).

Patrón igual al de agents-guide/react_agent.py:
  Thought → Action → Observation en un bucle, hasta Finish o máximo de pasos.

Las herramientas son funciones Python (db_tools): esquema y ejecutar SELECT.
El modelo escribe el SQL; no hay un segundo LLM dentro de las tools.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from agents.playground.db_tools import (
    execute_readonly_query,
    get_database_schema,
)

load_dotenv()

logger = logging.getLogger(__name__)

_ENV_VERBOSE_OK = frozenset({"1", "true", "yes", "on"})

_VERBOSE_THOUGHT_MAX = 6_000
_VERBOSE_OBS_MAX = 12_000
_VERBOSE_ARG_MAX = 8_000


def _resolve_verbose(verbose: bool | None) -> bool:
    if verbose is not None:
        return verbose
    return os.getenv("DB_REACT_VERBOSE", "").strip().lower() in _ENV_VERBOSE_OK


def _verbose_clip(label: str, text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n  … [{label}: omitidos ~{omitted} caracteres]"


def _print_trace_header(question: str) -> None:
    print()
    print("═" * 60)
    print(" DB ReAct · trazado de razonamiento (paso a paso)")
    print("─" * 60)
    print("Pregunta del usuario:")
    for line in question.strip().splitlines() or [""]:
        print(f"  {line}")
    print("═" * 60)
    print()


def _print_trace_step(
    step: int,
    thought: str,
    call: ToolCall,
    observation: str | None,
    *,
    raw_action_line: str | None = None,
) -> None:
    print(f"── Paso {step} ──")
    print("Pensamiento (Thought):")
    print(_verbose_clip("Thought", thought, _VERBOSE_THOUGHT_MAX))
    print()
    if raw_action_line:
        print(f"Modelo (Action {step}, texto completo):")
        print(_verbose_clip("Action", raw_action_line, _VERBOSE_ARG_MAX))
        print()
    print(f"Herramienta elegida: {call.tool}")
    if call.tool == "error":
        print("Detalle:")
        print(_verbose_clip("error", call.argument, _VERBOSE_ARG_MAX))
    elif call.tool == "Finish":
        print("Respuesta final (no hay Observation en este paso):")
        print(_verbose_clip("Finish", call.argument, _VERBOSE_ARG_MAX))
    else:
        arg_label = "SQL" if call.tool == "execute_readonly_query" else "argumento"
        print(f"{arg_label.capitalize()} (parseado para la tool):")
        print(_verbose_clip("argumento", call.argument, _VERBOSE_ARG_MAX))
    if observation is not None:
        print()
        print("Observación (salida de la herramienta):")
        print(_verbose_clip("Observation", observation, _VERBOSE_OBS_MAX))
    print()


DB_REACT_SYSTEM_PROMPT = """\
Eres un analista de datos experto en PostgreSQL. La empresa es un reseller de productos Apple.

Responde la pregunta del usuario usando las herramientas. No inventes cifras: solo lo que \
aparezca en las observaciones tras ejecutar SQL.

Tablas permitidas (nombres exactos en la base):
employees, customers, products, invoices, invoice_items

Herramientas — en cada paso usa UNA acción con este formato exacto:

1) get_database_schema[LISTA]
   - Lista vacía: get_database_schema[]  → esquema de todas las tablas permitidas.
   - Una tabla: get_database_schema[invoices]
   - Varias: get_database_schema[invoices,customers]  (separadas por coma, sin espacios)

2) execute_readonly_query[SQL]
   - Un solo SELECT o WITH ... (consulta de lectura). Sin punto y coma.
   - En literales SQL usa comillas simples '2026-04-01', no dobles dentro del SQL.

3) Finish[respuesta]
   - Texto final en español para el usuario, usando datos de las observaciones cuando haya.

Buen flujo:
- Si no sabes los nombres de columnas → get_database_schema primero (solo tablas que necesites).
- Luego execute_readonly_query con un SELECT válido.
- Si la observación dice error de SQL o validación, corrígelo y reintenta.
- Cuando tengas la información → Finish[...] con un único par de corchetes que abra y cierre la respuesta completa.

Límites:
- Máximo {max_steps} pasos (cada paso = un Thought y un Action).
- Cada respuesta tuya debe contener SOLO estas dos líneas (línea 1 y 2), sin markdown:
Thought N: ...
Action N: ...

Ejemplo (N es el número de paso, 1, 2, 3...):
Thought 1: Necesito el esquema de invoices para ver la columna de fecha.
Action 1: get_database_schema[invoices]

Tras cada Action recibirás:
Observation N: (texto que devuelve la herramienta)
"""


@dataclass
class ToolCall:
    tool: str
    argument: str


@dataclass
class ToolResult:
    output: str
    success: bool


def _strip_finish_quotes(inner: str) -> str:
    s = inner.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1].strip()
    return s


def parse_db_action(action_line: str) -> ToolCall:
    text = action_line.strip()
    if not text:
        return ToolCall("error", "Línea de acción vacía.")

    lower = text.lower()
    if lower.startswith("finish"):
        if "[" not in text or "]" not in text:
            return ToolCall("error", "Finish debe tener forma Finish[respuesta].")
        inner = text[text.index("[") + 1 : text.rindex("]")]
        return ToolCall("Finish", _strip_finish_quotes(inner))

    if text.startswith("get_database_schema"):
        if "[" not in text or "]" not in text:
            return ToolCall("error", "get_database_schema debe tener corchetes: get_database_schema[]")
        inner = text[text.index("[") + 1 : text.rindex("]")]
        return ToolCall("get_database_schema", inner.strip())

    if text.startswith("execute_readonly_query"):
        if "[" not in text or "]" not in text:
            return ToolCall(
                "error",
                "execute_readonly_query debe tener forma execute_readonly_query[SELECT ...]",
            )
        inner = text[text.index("[") + 1 : text.rindex("]")]
        return ToolCall("execute_readonly_query", inner.strip().strip('"'))

    return ToolCall(
        "error",
        f"No se reconoció la herramienta. Usa get_database_schema, execute_readonly_query o Finish. Texto: {text[:200]}",
    )


def execute_db_tool(call: ToolCall) -> ToolResult:
    if call.tool == "error":
        return ToolResult(call.argument, False)

    if call.tool == "Finish":
        return ToolResult(call.argument, True)

    try:
        if call.tool == "get_database_schema":
            out = get_database_schema(call.argument)
            return ToolResult(out, True)
        if call.tool == "execute_readonly_query":
            out = execute_readonly_query(call.argument)
            return ToolResult(out, True)
    except Exception as e:
        logger.exception("Error en herramienta %s", call.tool)
        return ToolResult(f"Error interno al ejecutar la herramienta: {e}", True)

    return ToolResult(f"Herramienta desconocida: {call.tool}", False)


class DBReactAgent:
    """
    Bucle ReAct contra Postgres.

    verbose=True (o DB_REACT_VERBOSE=1) imprime trazado en texto plano, sin códigos ANSI.
    """

    def __init__(
        self,
        model: str | None = None,
        max_steps: int = 20,
        timeout: float = 60.0,
    ):
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.max_steps = max_steps
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY no está definida.")
        self.client = OpenAI(
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=api_key,
            timeout=timeout,
        )

    def run(self, question: str, verbose: bool | None = None) -> dict:
        verbose = _resolve_verbose(verbose)
        trajectory = f"Question: {question}\n"
        system = DB_REACT_SYSTEM_PROMPT.format(max_steps=self.max_steps)
        steps: list[dict] = []

        if verbose:
            _print_trace_header(question)

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
                logger.error("LLM paso %s: %s", step, e)
                if verbose:
                    print(f"── Paso {step} ── ERROR al llamar al modelo: {e}\n")
                steps.append({"step": step, "error": str(e)})
                return {
                    "answer": None,
                    "steps": steps,
                    "trajectory": trajectory,
                    "error": str(e),
                }

            thought, action_line = self._parse_react_output(raw, step)
            call = parse_db_action(action_line)

            logger.debug("Paso %s thought=%s action=%s", step, thought[:80], action_line[:80])

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
                if verbose:
                    print("═" * 60)
                    print(" Fin ReAct: respuesta entregada al usuario (Finish)")
                    print("═" * 60 + "\n")
                return {
                    "answer": call.argument,
                    "steps": steps,
                    "trajectory": trajectory,
                }

            result = execute_db_tool(call)
            observation = result.output

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

        logger.warning("DB ReAct: se alcanzó max_steps=%s sin Finish", self.max_steps)
        if verbose:
            print("═" * 60)
            print(f" Fin ReAct: se alcanzó el máximo de pasos ({self.max_steps}) sin Finish.")
            print("═" * 60 + "\n")
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
        """Thought / Action por paso, con respaldo de extraer la llamada con corchetes."""
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


def run_db_react_agent(
    question: str,
    *,
    max_steps: int = 8,
    verbose: bool | None = None,
    model: str | None = None,
) -> str | None:
    agent = DBReactAgent(model=model, max_steps=max_steps)
    result = agent.run(question, verbose=verbose)
    return result.get("answer")
