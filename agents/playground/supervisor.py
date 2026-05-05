import logging
import json
import operator
import re
import os
import sys
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4

# Raíz del repo en sys.path antes de `from rag...` (funciona con
# `python3 agents/playground/supervisor.py` desde cualquier cwd razonable).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from typing_extensions import TypedDict, Annotated, NotRequired
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Carga .env desde la raíz del repo aunque el cwd sea otro directorio
load_dotenv(_REPO_ROOT / ".env")
from langchain_core.messages import (
    AnyMessage,
    SystemMessage,
    HumanMessage,
)
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# ─── ESTADO COMPARTIDO ──────────────────────────────────────
class CustomerState(TypedDict):
    """Estado compartido entre el supervisor y los workers."""
    messages: Annotated[list[AnyMessage], operator.add]
    # Clasificación del supervisor
    rag_query_question: str
    db_query_question: str
    cotizacion_query_question: str
    greeting_query: str
    # Auditoría del verificador de clasificación (opcional)
    classification_confidence: NotRequired[float]
    classification_review_reason: NotRequired[str]
    # Respuestas de cada worker
    rag_query_response: str
    db_query_response: str
    cotizacion_response: str
    greeting_response: str
    # Cotización: borrador persistido (reanudación HITL sin re-ejecutar ReAct)
    cotizacion_draft: NotRequired[str]
    cotizacion_original_query: NotRequired[str]
    cotizacion_review_round: NotRequired[int]
    # Instrucciones para repetir el ReAct completo (feedback del vendedor); se consume en quote_draft_agent.
    cotizacion_react_input: NotRequired[str]
    # PDF fpdf2 tras aprobación vendedor (ruta absoluta o vacío)
    cotizacion_pdf_path: NotRequired[str]
    # Respuesta final
    final_response: str


# ─── LLM via Groq (OpenAI-compatible) ───────────────────────

_GROQ_BASE = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
_DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

llm = ChatOpenAI(
    model=_DEFAULT_GROQ_MODEL,
    api_key=os.getenv("GROQ_API_KEY"),
    base_url=_GROQ_BASE,
    temperature=0,
    max_tokens=2048,
)
check_categoritzation_llm = ChatOpenAI(
    model=os.getenv("GROQ_MODEL_CHECK", _DEFAULT_GROQ_MODEL),
    api_key=os.getenv("GROQ_API_KEY"),
    base_url=_GROQ_BASE,
    temperature=0,
    max_tokens=2048,
)

CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.99

# Rondas máximas revisión vendedor ↔ cotización (interrupt).
QUOTE_REVIEW_MAX_ROUNDS = 12

# ANSI para resumen tras verificación de clasificación (asses node)
_C_BL = "\033[1m"
_C_DIM = "\033[2m"
_C_CYAN = "\033[96m"
_C_MAG = "\033[95m"
_C_GOLD = "\033[93m"
_C_GRN = "\033[92m"
_C_BLUE = "\033[94m"
_C_RST = "\033[0m"


def _format_supervisor_categories(rag: str, db: str, cot: str, gr: str) -> str:
    parts: list[str] = []
    if cot.strip():
        parts.append("Cotización")
    if rag.strip():
        parts.append("RAG")
    if db.strip():
        parts.append("Base de datos")
    if gr.strip():
        parts.append("Saludo")
    return " · ".join(parts) if parts else "—"


def _print_classification_review(
    user_msg: str,
    rag: str,
    db: str,
    cot: str,
    gr: str,
    confidence: float,
    brief_reason: str,
) -> None:
    cat = _format_supervisor_categories(rag, db, cot, gr)
    reason = (brief_reason or "").strip() or "—"
    print()
    print(f"{_C_BL}{_C_CYAN}Pregunta:{_C_RST} {_C_DIM}{user_msg}{_C_RST}")
    print(f"{_C_BL}{_C_MAG}Categoría:{_C_RST} {_C_GRN}{cat}{_C_RST}")
    print(f"{_C_BL}{_C_GOLD}Puntaje:{_C_RST} {_C_GRN}{confidence:.2f}{_C_RST}")
    print(f"{_C_BL}{_C_BLUE}Razón:{_C_RST} {_C_DIM}{reason}{_C_RST}")
    print()


class QuestionClassification(BaseModel):
    """Una sola categoría por mensaje: solo un campo distinto de vacío."""
    rag_query: str = Field(
        default="",
        description="Conocimiento interno/políticas; vacío si no aplica.",
    )
    db_query: str = Field(
        default="",
        description="Datos en BD (ventas, inventario, etc.); vacío si no aplica.",
    )
    greeting_query: str = Field(
        default="",
        description="Solo saludo/cortesía sin negocio; vacío si no aplica.",
    )
    cotizacion_query: str = Field(
        default="",
        description="Pedido de cotización/presupuesto con productos y cantidades.",
    )


def _collapse_to_single_category(
    result: QuestionClassification,
    user_msg_raw: object,
) -> tuple[str, str, str, str]:
    """
    Como mucho un campo no vacío. Prioridad si hay varios llenos: cotización > BD > RAG > saludo.
    """
    full = (user_msg_raw if isinstance(user_msg_raw, str) else str(user_msg_raw or "")).strip()
    rag = result.rag_query.strip()
    db = result.db_query.strip()
    cot = result.cotizacion_query.strip()
    gr = result.greeting_query.strip()
    if sum(1 for s in (rag, db, cot, gr) if s) <= 1:
        return rag, db, cot, gr
    if cot:
        return "", "", full, ""
    if db:
        return "", full, "", ""
    if rag:
        return full, "", "", ""
    return "", "", "", full


def _parse_classification_json(raw: str) -> QuestionClassification:
    """
    Extrae QuestionClassification desde la salida del modelo como JSON en texto.
    Compatible con modelos Groq que no soportan response_format json_schema (p. ej. Llama).
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No se encontró un objeto JSON en la respuesta del clasificador.")
    blob = text[start : end + 1]
    data = json.loads(blob)
    if not isinstance(data, dict):
        raise ValueError("El JSON del clasificador no es un objeto.")
    return QuestionClassification(
        rag_query=str(data.get("rag_query") or ""),
        db_query=str(data.get("db_query") or ""),
        cotizacion_query=str(data.get("cotizacion_query") or ""),
        greeting_query=str(data.get("greeting_query") or ""),
    )


class ClassificationReview(BaseModel):
    """Confianza en que la ÚNICA categoría elegida es correcta para el mensaje completo."""
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confianza en que la categoría única elegida es correcta.",
    )
    brief_reason: str = Field(
        default="",
        description="Justificación breve en español.",
    )


def _parse_review_json(raw: str) -> ClassificationReview:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No se encontró JSON del verificador de clasificación.")
    blob = text[start : end + 1]
    data = json.loads(blob)
    if not isinstance(data, dict):
        raise ValueError("El JSON del verificador no es un objeto.")
    conf = data.get("confidence", 0)
    try:
        confidence = float(conf)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    return ClassificationReview(
        confidence=confidence,
        brief_reason=str(data.get("brief_reason") or ""),
    )


def supervisor(state: CustomerState) -> dict:
    user_msg = state["messages"][-1].content

    # No usar with_structured_output: en Groq usa json_schema y muchos modelos (Llama) no lo soportan.
    try:
        reply = llm.invoke([
            SystemMessage(content=(
                "Eres supervisor de atención al cliente (tienda Apple). "
                "Clasificas cada mensaje del cliente en EXACTAMENTE UNA de cuatro categorías.\n\n"
                "REGLAS OBLIGATORIAS:\n"
                "- Solo UNO de los cuatro campos del JSON puede tener texto; los otros TRES deben ser \"\".\n"
                "- En el campo elegido copias el mensaje COMPLETO del cliente.\n\n"
                "Categorías (elige UNA):\n"
                "- cotizacion_query: pedir cotización, presupuesto, precio por volumen/cantidades "
                "(ej. \"10 MacBooks y 5 iPhones\").\n"
                "- db_query: datos históricos u operativos en BD sin pedir cotización "
                "(ventas pasadas, inventario como número exacto de consulta, clientes).\n"
                "- rag_query: políticas, garantías, procedimientos según manuales.\n"
                "- greeting_query: solo saludo o charla sin consulta de negocio.\n\n"
                "Prioridad conceptual si el mensaje mezcla temas: cotización sobre BD sobre RAG sobre saludo.\n\n"
                "Responde ÚNICAMENTE con JSON válido, sin markdown:\n"
                '{"rag_query":"","db_query":"","cotizacion_query":"","greeting_query":""}'
            )),
            HumanMessage(content=f"Mensaje del cliente:\n{user_msg}"),
        ])
        raw_text = reply.content if isinstance(reply.content, str) else str(reply.content or "")
        result = _parse_classification_json(raw_text)
        rag_o, db_o, cot_o, gr_o = _collapse_to_single_category(result, user_msg)
    except Exception as e:
        logger.exception("Error al clasificar la pregunta")
        print(f"Error al clasificar la pregunta: {e}")
        return {
            "rag_query_question": "",
            "db_query_question": "",
            "cotizacion_query_question": "",
            "greeting_query": "",
        }

    return {
        "rag_query_question": rag_o,
        "db_query_question": db_o,
        "cotizacion_query_question": cot_o,
        "greeting_query": gr_o,
    }


def _apply_human_classification(decision: dict) -> dict:
    """Reescribe rutas según la decisión humana tras interrupt."""
    cat = str(decision.get("category") or "").strip().lower()
    q = str(
        decision.get("extracted_question")
        or decision.get("pregunta")
        or decision.get("question")
        or "",
    ).strip()
    if cat == "quote":
        cat = "cotizacion"
    if cat not in ("rag", "db", "greeting", "cotizacion"):
        logger.warning("Categoría HITL inválida %r; se usa greeting.", cat)
        cat = "greeting"
    if not q:
        logger.warning("extracted_question vacío en decisión HITL.")
    rag_q, db_q, cot_q, gr_q = "", "", "", ""
    if cat == "rag":
        rag_q = q
    elif cat == "db":
        db_q = q
    elif cat == "cotizacion":
        cot_q = q
    else:
        gr_q = q
    return {
        "rag_query_question": rag_q,
        "db_query_question": db_q,
        "cotizacion_query_question": cot_q,
        "greeting_query": gr_q,
        "classification_confidence": 1.0,
        "classification_review_reason": "Corregido manualmente (HITL).",
    }


def assess_categorization(state: CustomerState) -> dict:
    """
    Valida la clasificación del supervisor con un modelo de chequeo.
    Si la confianza es baja, pausa con interrupt() para corrección humana.
    """
    rag = (state.get("rag_query_question") or "").strip()
    db = (state.get("db_query_question") or "").strip()
    cot = (state.get("cotizacion_query_question") or "").strip()
    gr = (state.get("greeting_query") or "").strip()

    user_content = state["messages"][-1].content
    user_msg = user_content if isinstance(user_content, str) else str(user_content)

    rag, db, cot, gr = _collapse_to_single_category(
        QuestionClassification(
            rag_query=rag,
            db_query=db,
            cotizacion_query=cot,
            greeting_query=gr,
        ),
        user_msg,
    )
    if not rag and not db and not cot and not gr:
        return {}

    confidence = 0.0
    brief_reason = ""

    try:
        reply = check_categoritzation_llm.invoke([
            SystemMessage(content=(
                "Eres verificador de clasificación (tienda Apple). "
                "El supervisor debe haber dejado EXACTAMENTE UNA categoría con texto y las demás vacías. "
                "Campos: rag_query_question, db_query_question, cotizacion_query_question, greeting_query.\n\n"
                "Evalúa si esa categoría única encaja con todo el mensaje:\n"
                "- cotización: presupuesto, cotizar, precio por cantidades de productos.\n"
                "- BD: consultas de datos históricos/inventario sin armar cotización.\n"
                "- RAG: políticas/manuales.\n"
                "- saludo: solo cortesía.\n\n"
                "Si hay más de un campo con texto, clasificación incorrecta → confianza muy baja.\n\n"
                "Responde ÚNICAMENTE con JSON válido, sin markdown: "
                '{"confidence": <float 0 a 1>, "brief_reason": "<breve en español>"}'
            )),
            HumanMessage(content=json.dumps({
                "mensaje_cliente": user_msg,
                "rag_query_question": rag,
                "db_query_question": db,
                "cotizacion_query_question": cot,
                "greeting_query": gr,
            }, ensure_ascii=False)),
        ])
        raw_text = reply.content if isinstance(reply.content, str) else str(reply.content or "")
        review = _parse_review_json(raw_text)
        confidence = review.confidence
        brief_reason = review.brief_reason.strip()
    except Exception:
        logger.exception("Fallo del verificador de clasificación")
        confidence = 0.0
        brief_reason = "Error al validar la clasificación automática."

    passed = confidence >= CLASSIFICATION_CONFIDENCE_THRESHOLD
    if passed:
        _print_classification_review(user_msg, rag, db, cot, gr, confidence, brief_reason)
        return {
            "rag_query_question": rag,
            "db_query_question": db,
            "cotizacion_query_question": cot,
            "greeting_query": gr,
            "classification_confidence": confidence,
            "classification_review_reason": brief_reason,
        }

    payload = {
        "action": "classification_review",
        "message": (
            "La confianza del verificador es baja. Elija la categoría correcta y el texto "
            "de la consulta a enrutar."
        ),
        "original_user_message": user_msg,
        "supervisor_classification": {
            "rag_query_question": rag,
            "db_query_question": db,
            "cotizacion_query_question": cot,
            "greeting_query": gr,
        },
        "validator_confidence": confidence,
        "brief_reason": brief_reason,
        "resume_hint": (
            "El cliente del grafo enviará category + extracted_question (p. ej. desde CLI en dos pasos)."
        ),
    }
    human_decision = interrupt(payload)
    if not isinstance(human_decision, dict):
        human_decision = {}
    out = _apply_human_classification(human_decision)
    _print_classification_review(
        user_msg,
        out["rag_query_question"],
        out["db_query_question"],
        out.get("cotizacion_query_question") or "",
        out["greeting_query"],
        float(out.get("classification_confidence", 1.0)),
        brief_reason,
    )
    return out


def route_after_supervisor(
    state: CustomerState,
) -> Literal["rag_agent", "db_agent", "quote_draft_agent", "greeting_agent", "end"]:
    """
    Prioridad: cotización → RAG → datos → saludo → fin.
    """
    if (state.get("cotizacion_query_question") or "").strip():
        return "quote_draft_agent"
    if (state.get("rag_query_question") or "").strip():
        return "rag_agent"
    if (state.get("db_query_question") or "").strip():
        return "db_agent"
    if (state.get("greeting_query") or "").strip():
        return "greeting_agent"
    return "end"


def rag_agent(state: CustomerState) -> dict:
    q = (state.get("rag_query_question") or "").strip()
    if not q:
        q = str(state["messages"][-1].content)

    try:
        from rag.main_rag_pipeline_v2 import answer_rag_query

        answer = answer_rag_query(q, compress_with_llm=False)
        return {"rag_query_response": answer}
    except Exception:
        logger.exception("RAG worker: fallo al ejecutar el pipeline")
        fallback = llm.invoke([
            SystemMessage(content=(
                "Eres el canal de atención al cliente de un comercio de productos Apple. "
                "Por un inconveniente técnico temporal no pudimos consultar la base de conocimiento. "
                "Responde en español, tono formal y breve: pide disculpas, indica que puede "
                "intentar de nuevo más tarde y ofrece contactar a un asesor. "
                "No inventes políticas ni datos de la empresa."
            )),
            HumanMessage(
                content=f"El cliente preguntó lo siguiente (no respondas el contenido literal; solo el mensaje de servicio): {q}"
            ),
        ])
        return {"rag_query_response": fallback.content}


def db_agent(state: CustomerState) -> dict:
    """
    Preguntas clasificadas como consultas a la base (ventas, clientes, inventario, etc.).
    Usa un bucle ReAct: esquema → SQL de solo lectura → respuesta en lenguaje natural.
    """
    q = (state.get("db_query_question") or "").strip()
    if not q:
        q = str(state["messages"][-1].content)

    try:
        from agents.playground.db_react_agent import run_db_react_agent

        answer = run_db_react_agent(q, max_steps=20)
        if not answer:
            raise ValueError("El agente de datos no llegó a una respuesta final (Finish).")
        return {"db_query_response": answer}
    except Exception:
        logger.exception("DB worker: fallo el agente ReAct o la conexión")
        fallback = llm.invoke([
            SystemMessage(content=(
                "Eres el canal de atención al cliente de un comercio de productos Apple. "
                "No pudimos consultar la base de datos en este momento (error técnico o timeout). "
                "Responde en español, tono formal y breve: disculpas, sugerir intentar más tarde "
                "y ofrecer que un asesor revise el caso. No inventes cifras ni datos de inventario/ventas."
            )),
            HumanMessage(
                content=(
                    "La consulta del cliente era sobre datos/tienda (no repitas su texto literal; "
                    "solo el mensaje de servicio): "
                    f"{q[:500]}"
                )
            ),
        ])
        return {"db_query_response": fallback.content}


def quote_draft_agent(state: CustomerState) -> dict:
    """
    Ejecuta el ReAct de cotización (traza completa). Primera vez usa la pregunta clasificada;
    si existe cotizacion_react_input (feedback de revisión), re-ejecuta todo el razonamiento con ese texto.
    """
    regen = (state.get("cotizacion_react_input") or "").strip()

    if regen:
        q_for_react = regen
        orig = (state.get("cotizacion_original_query") or "").strip()
        round_keep = int(state.get("cotizacion_review_round") or 0)
    else:
        q_for_react = (state.get("cotizacion_query_question") or "").strip()
        if not q_for_react:
            q_for_react = str(state["messages"][-1].content)
        orig = q_for_react
        round_keep = 0

    from agents.playground.quote_react_agent import run_quote_react_agent

    try:
        draft = run_quote_react_agent(q_for_react, max_steps=24)
        if not draft:
            raise ValueError("El agente de cotización no devolvió contenido.")
    except Exception:
        logger.exception(
            "Quote worker: fallo el agente de cotización o la conexión "
            f"({'regeneración' if regen else 'borrador inicial'})"
        )
        ctx = q_for_react[:500] if len(q_for_react) > 500 else q_for_react
        fallback = llm.invoke([
            SystemMessage(content=(
                "Eres el canal de atención al cliente de un comercio de productos Apple. "
                "No pudimos generar la cotización en este momento (error técnico o timeout). "
                "Responde en español, tono formal y breve: disculpas y que un asesor puede ayudar. "
                "No inventes precios ni líneas de cotización."
            )),
            HumanMessage(content=f"Contexto (solo tono servicio, sin cotizar): {ctx}"),
        ])
        return {
            "cotizacion_response": fallback.content,
            "cotizacion_react_input": "",
        }

    out: dict = {
        "cotizacion_draft": draft,
        "cotizacion_react_input": "",
        "cotizacion_original_query": orig
        or (state.get("cotizacion_original_query") or "").strip()
        or q_for_react,
        "cotizacion_review_round": round_keep,
    }
    return out


def _route_after_quote_draft(
    state: CustomerState,
) -> Literal["quote_review_agent", "end"]:
    if (state.get("cotizacion_response") or "").strip():
        return "end"
    return "quote_review_agent"


def quote_review_agent(state: CustomerState) -> dict:
    """
    Solo HITL: interrupt y aprobación sin ReAct. El feedback del vendedor delega el re-razonamiento
    completo a quote_draft_agent vía cotizacion_react_input.
    """
    draft = (state.get("cotizacion_draft") or "").strip()
    q = (
        (state.get("cotizacion_original_query") or "").strip()
        or (state.get("cotizacion_query_question") or "").strip()
    )
    if not q:
        q = str(state["messages"][-1].content)

    if not draft:
        logger.warning("quote_review_agent: sin cotizacion_draft en estado.")
        fb = llm.invoke([
            SystemMessage(content=(
                "Eres el canal de atención al cliente de un comercio de productos Apple. "
                "No hay borrador de cotización para revisar (estado inconsistente). "
                "Responde en español, breve: pida disculpas y que un asesor continúe."
            )),
            HumanMessage(content=f"Contexto: {q[:500]}"),
        ])
        return {"cotizacion_response": fb.content}

    round_idx = int(state.get("cotizacion_review_round") or 0)

    if round_idx >= QUOTE_REVIEW_MAX_ROUNDS:
        suffix = (
            "\n\n---\n_Notificación interna: se alcanzó el máximo de rondas de revisión "
            "con el vendedor; valide esta versión fuera del flujo automático si aplica._"
        )
        return {
            "cotizacion_response": draft + suffix,
            "cotizacion_draft": "",
            "cotizacion_review_round": 0,
        }

    decision = interrupt({
        "action": "quote_review",
        "revision_round": round_idx + 1,
        "max_rounds_hint": QUOTE_REVIEW_MAX_ROUNDS,
        "message": (
            "Revise la cotización como vendedor. Solo después de su aprobación se "
            "considera definitiva para el cliente."
        ),
        "cotizacion_markdown": draft,
        "original_client_query": q,
    })
    if not isinstance(decision, dict):
        decision = {}

    if decision.get("approved") is True:
        out: dict = {
            "cotizacion_response": draft,
            "cotizacion_draft": "",
            "cotizacion_review_round": 0,
        }
        try:
            from pdf.cotization_generator import write_pdf_on_quote_approval

            pdf_path = write_pdf_on_quote_approval(draft)
            if pdf_path:
                out["cotizacion_pdf_path"] = pdf_path
        except Exception:
            logger.exception(
                "No se pudo generar el PDF de cotización aprobada (fpdf2). "
                "La cotización en texto sigue siendo válida."
            )
        return out

    replacement = (decision.get("replacement_markdown") or "").strip()
    feedback = (decision.get("feedback") or "").strip()

    if replacement:
        return {
            "cotizacion_draft": replacement,
            "cotizacion_review_round": round_idx + 1,
        }

    if feedback:
        augmented = (
            f"{q}\n\n---\nCotización actual (referencia):\n{draft}\n\n"
            f"Instrucciones del vendedor para regenerar:\n{feedback}"
        )
        return {
            "cotizacion_react_input": augmented,
            "cotizacion_review_round": round_idx + 1,
        }

    return {"cotizacion_review_round": round_idx + 1}


def _route_after_quote_review(
    state: CustomerState,
) -> Literal["quote_draft_agent", "quote_review_agent", "end"]:
    if (state.get("cotizacion_response") or "").strip():
        return "end"
    if (state.get("cotizacion_react_input") or "").strip():
        return "quote_draft_agent"
    return "quote_review_agent"


def greeting_agent(state: CustomerState) -> dict:
    q = (state.get("greeting_query") or "").strip()
    if not q:
        q = str(state["messages"][-1].content)

    response = llm.invoke([
        SystemMessage(content=(
            "Eres un asistente de atencion al cliente de una empresa de venta de productos de tecnologia apple que responde preguntas de saludo o conversacion casual."
            "Debes usar jerga colombiana de medellin."
            "Debe ser respetuoso."
            "No debes de responder preguntas o temas relacionados con la empresa o productos."
        )),
        HumanMessage(content=q),
    ])
    return {"greeting_response": response.content}


def build_customer_agent(checkpointer: MemorySaver | None = None):
    workflow = StateGraph(CustomerState)
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("assess_categorization", assess_categorization)
    workflow.add_node("rag_agent", rag_agent)
    workflow.add_node("db_agent", db_agent)
    workflow.add_node("quote_draft_agent", quote_draft_agent)
    workflow.add_node("quote_review_agent", quote_review_agent)
    workflow.add_node("greeting_agent", greeting_agent)

    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "assess_categorization")
    workflow.add_conditional_edges(
        "assess_categorization",
        route_after_supervisor,
        {
            "rag_agent": "rag_agent",
            "db_agent": "db_agent",
            "quote_draft_agent": "quote_draft_agent",
            "greeting_agent": "greeting_agent",
            "end": END,
        },
    )
    workflow.add_conditional_edges(
        "quote_draft_agent",
        _route_after_quote_draft,
        {
            "quote_review_agent": "quote_review_agent",
            "end": END,
        },
    )
    workflow.add_conditional_edges(
        "quote_review_agent",
        _route_after_quote_review,
        {
            "quote_draft_agent": "quote_draft_agent",
            "quote_review_agent": "quote_review_agent",
            "end": END,
        },
    )
    workflow.add_edge("rag_agent", END)
    workflow.add_edge("db_agent", END)
    workflow.add_edge("greeting_agent", END)
    ckpt = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=ckpt)


customer_agent = build_customer_agent()


def format_classification_interrupt(payload: dict) -> str:
    """Texto legible y con color para el CLI cuando hay interrupt de clasificación."""
    conf = float(payload.get("validator_confidence", 0) or 0)
    reason = str(payload.get("brief_reason", "") or "")
    client_msg = str(payload.get("original_user_message", "") or "")
    sup_json = json.dumps(
        payload.get("supervisor_classification") or {},
        ensure_ascii=False,
        indent=2,
    )
    lbl = f"{_C_BL}{_C_MAG}"
    title = f"{_C_BL}{_C_GOLD}━━━ Clasificación dudosa (requiere su decisión) ━━━{_C_RST}"
    sys_msg = str(payload.get("message", "") or "").strip()

    parts = [
        "",
        title,
        "",
    ]
    if sys_msg:
        parts.extend([
            f"{lbl}Aviso:{_C_RST} {_C_DIM}{sys_msg}{_C_RST}",
            "",
        ])
    parts.extend([
        f"{lbl}Confianza automática:{_C_RST} {_C_GRN}{conf:.2f}{_C_RST}",
        f"{lbl}Motivo:{_C_RST} {_C_DIM}{reason}{_C_RST}",
        "",
        f"{lbl}Mensaje del cliente:{_C_RST}",
        f"{_C_DIM}{client_msg}{_C_RST}",
        "",
        f"{lbl}Clasificación del supervisor:{_C_RST}",
        f"{_C_DIM}{sup_json}{_C_RST}",
        "",
        f"{_C_BL}{_C_CYAN}Siguiente:{_C_RST} {_C_DIM}"
        f"elija categoría y el texto que verá el agente (dos pasos).{_C_RST}",
        "",
    ])
    return "\n".join(parts)


def format_quote_review_interrupt(payload: dict) -> str:
    """Salida coloreada para revisión humana obligatoria de cotización."""
    rnd = int(payload.get("revision_round") or 1)
    mx = int(payload.get("max_rounds_hint") or 12)
    msg = str(payload.get("message") or "").strip()
    query = str(payload.get("original_client_query") or "").strip()
    body = str(payload.get("cotizacion_markdown") or "")
    lbl = f"{_C_BL}{_C_MAG}"
    title = f"{_C_BL}{_C_GOLD}━━━ Revisión vendedor — cotización (ronda {rnd}/{mx}) ━━━{_C_RST}"

    parts: list[str] = ["", title, ""]
    if msg:
        parts.extend([f"{lbl}Instrucción:{_C_RST} {_C_DIM}{msg}{_C_RST}", ""])
    parts.extend([
        f"{lbl}Pedido del cliente:{_C_RST}",
        f"{_C_DIM}{query}{_C_RST}",
        "",
        f"{lbl}Borrador actual:{_C_RST}",
        f"{_C_DIM}{body}{_C_RST}",
        "",
        f"{_C_BL}{_C_CYAN}Menú{_C_RST} {_C_DIM}(siguiente línea){_C_RST}",
        "",
    ])
    return "\n".join(parts)


def invoke_customer_agent(
    query: str,
    *,
    thread_id: str | None = None,
    resolve_interrupt: Callable[[dict], dict] | None = None,
) -> dict:
    """
    Ejecuta el grafo del cliente. Si hay interrupt y `resolve_interrupt` está definido,
    reanuda en bucle hasta terminar.
    """
    tid = thread_id or str(uuid4())
    config: dict = {"configurable": {"thread_id": tid}}
    initial_state: CustomerState = {
        "messages": [HumanMessage(content=query)],
        "rag_query_question": "",
        "db_query_question": "",
        "cotizacion_query_question": "",
        "greeting_query": "",
        "rag_query_response": "",
        "db_query_response": "",
        "cotizacion_response": "",
        "greeting_response": "",
        "final_response": "",
    }

    result = customer_agent.invoke(initial_state, config)
    while result.get("__interrupt__") and resolve_interrupt is not None:
        intr = result["__interrupt__"][0]
        payload = intr.value if hasattr(intr, "value") else intr
        resume_val = resolve_interrupt(payload if isinstance(payload, dict) else {})
        result = customer_agent.invoke(Command(resume=resume_val), config)
    return result


if __name__ == "__main__":
    from agents.playground.interactive_chat import customer_invoke_with_hitl, main_interactive

    main_interactive(customer_invoke_with_hitl)