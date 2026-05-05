"""
CLI interactivo multilínea para probar el supervisor.
Mantiene los prompts y el ciclo de entrada separados del grafo.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

_CYAN = "\033[36m"
_RESET = "\033[0m"
_BL = "\033[1m"
_MAG = "\033[95m"
def _prompt_done() -> str:
    """Pregunta si el usuario terminó de escribir. Devuelve 's', 'n' o 'exit'."""
    while True:
        raw = input(
            "  ¿Ya quedó listo con eso o le falta algo más? [s/n] "
            "(exit si quiere salir): "
        ).strip().lower()
        if raw in ("exit", "quit", "salir"):
            return "exit"
        if raw in ("s", "si", "sí", "y", "yes"):
            return "s"
        if raw in ("n", "no"):
            return "n"
        print("  Uy parce, ponga s, n o exit, ¿sí me explico?")


def _read_multiline_message() -> str | None:
    """
    Acumula líneas hasta confirmación con 's'.
    None = salir del programa.
    """
    lines: list[str] = []
    while True:
        line = input(
            "  Meta acá una línea de su mensaje (Enter; 'exit' pa salir): "
        )
        if line.strip().lower() in ("exit", "quit", "salir"):
            return None
        lines.append(line)
        choice = _prompt_done()
        if choice == "exit":
            return None
        if choice == "s":
            return "\n".join(lines).strip()
        # choice == "n": seguir añadiendo líneas


def _print_playground_result(result: dict) -> None:
    """Salida legible: respuesta del agente que haya actuado; sin volcar el estado crudo."""
    cot = (result.get("cotizacion_response") or "").strip()
    pdf_path = (result.get("cotizacion_pdf_path") or "").strip()
    if cot:
        print(f"\n{_CYAN}{cot}{_RESET}\n")
        if pdf_path:
            print(f"{_BL}PDF (cotización aprobada):{_RESET} {pdf_path}\n")
        return

    rag_ans = (result.get("rag_query_response") or "").strip()
    if rag_ans:
        print(f"\n{_CYAN}{rag_ans}{_RESET}\n")
        return

    db_ans = (result.get("db_query_response") or "").strip()
    if db_ans:
        print(f"\n{_CYAN}{db_ans}{_RESET}\n")
        return

    greeting = (result.get("greeting_response") or "").strip()
    if greeting:
        print(f"\n{_CYAN}{greeting}{_RESET}\n")
        return

    rag_q = (result.get("rag_query_question") or "").strip()
    db_q = (result.get("db_query_question") or "").strip()
    cot_q = (result.get("cotizacion_query_question") or "").strip()
    parts: list[str] = []
    if cot_q:
        parts.append(f"Pendiente (cotización): {cot_q}")
    if rag_q:
        parts.append(f"Pendiente (RAG): {rag_q}")
    if db_q:
        parts.append(f"Pendiente (datos): {db_q}")
    if parts:
        print("\n" + "\n".join(parts) + "\n")
        return

    print("\n(No hubo respuesta ni clasificación útil en esta vuelta.)\n")


def _prompt_hitl_category() -> str | None:
    """Devuelve 'rag' | 'db' | 'cotizacion' | 'greeting', o None si sale."""
    print(f"\n  {_BL}{_MAG}Paso 1 — Categoría para el agente{_RESET}")
    print("    [1] RAG — políticas / conocimiento interno")
    print("    [2] Base de datos — ventas, inventario, datos en BD")
    print("    [3] Cotización — presupuesto / precios por cantidades")
    print("    [4] Saludo — solo cortesía / charla")
    print("    También puede escribir: rag, db, cotizacion (o quote), greeting")
    print(f"    ({_CYAN}exit{_RESET} para salir)\n")
    while True:
        raw = input("  Su elección: ").strip().lower()
        if raw in ("exit", "quit", "salir"):
            return None
        if raw in ("1", "rag", "r"):
            return "rag"
        if raw in ("2", "db", "d", "datos", "bd"):
            return "db"
        if raw in ("3", "cotizacion", "c", "cotización", "quote", "presupuesto"):
            return "cotizacion"
        if raw in ("4", "greeting", "g", "saludo"):
            return "greeting"
        print("  Use 1–4 o rag / db / cotizacion / greeting.\n")


def _resolve_classification_interrupt(payload: dict) -> dict:
    """Dos pasos: categoría y texto; arma el dict que espera el grafo."""
    from agents.playground.supervisor import format_classification_interrupt

    print(format_classification_interrupt(payload))

    while True:
        category = _prompt_hitl_category()
        if category is None:
            print("\nChao pues.\n")
            sys.exit(0)

        print(f"\n  {_BL}{_MAG}Paso 2 — Texto que recibirá el agente{_RESET}")
        print("    (multilínea como su mensaje principal; exit para salir)\n")
        extracted = _read_multiline_message()
        if extracted is None:
            print("\nChao pues.\n")
            sys.exit(0)
        extracted = extracted.strip()
        if not extracted:
            fb = str(payload.get("original_user_message") or "").strip()
            if fb:
                yn = input(
                    "  Quedó vacío. ¿Usar el mensaje original del cliente? [s/n]: "
                ).strip().lower()
                if yn in ("s", "si", "sí", "y", "yes"):
                    extracted = fb
            if not extracted:
                print("  Necesitamos un texto. Vuelva al paso 1.\n")
                continue

        return {"category": category, "extracted_question": extracted}


def _resolve_quote_review_interrupt(payload: dict) -> dict:
    """Vendedor aprueba, pide cambios (regenerar) o pega Markdown editado."""
    from agents.playground.supervisor import format_quote_review_interrupt

    print(format_quote_review_interrupt(payload))
    while True:
        print(f"\n  {_BL}{_MAG}¿Qué hace el vendedor?{_RESET}")
        print("    [1] Aprobar — esta cotización es la final para el cliente")
        print("    [2] Pedir cambios — describa ajustes (el agente regenera)")
        print("    [3] Reemplazar — pegue el Markdown completo editado por usted")
        print(f"    ({_CYAN}exit{_RESET} para salir)\n")
        choice = input("  Opción [1/2/3]: ").strip().lower()
        if choice in ("exit", "quit", "salir"):
            print("\nChao pues.\n")
            sys.exit(0)
        if choice in ("1", "s", "si", "sí", "aprobar", "ok", "y", "yes"):
            return {"approved": True}
        if choice == "2":
            print("\n  Describa los cambios (multilínea; exit para salir):\n")
            fb = _read_multiline_message()
            if fb is None:
                print("\nChao pues.\n")
                sys.exit(0)
            fb = fb.strip()
            if not fb:
                print("  Sin texto no puedo regenerar. Elija otra opción.\n")
                continue
            return {"approved": False, "feedback": fb}
        if choice == "3":
            print("\n  Pegue la cotización en Markdown (multilínea; exit para salir):\n")
            md = _read_multiline_message()
            if md is None:
                print("\nChao pues.\n")
                sys.exit(0)
            md = md.strip()
            if not md:
                print("  Está vacío. Elija otra opción.\n")
                continue
            return {"approved": False, "replacement_markdown": md}
        print("  Use 1, 2 o 3.\n")


def _dispatch_resolve_interrupt(payload: dict) -> dict:
    act = str(payload.get("action") or "")
    if act == "quote_review":
        return _resolve_quote_review_interrupt(payload)
    return _resolve_classification_interrupt(payload)


def customer_invoke_with_hitl(query: str) -> dict:
    """Invoca el grafo con HITL para clasificación dudosa y revisión de cotización."""
    from agents.playground.supervisor import invoke_customer_agent

    return invoke_customer_agent(query, resolve_interrupt=_dispatch_resolve_interrupt)


def main_interactive(invoke_agent: Callable[[str], dict]) -> None:
    """
    Ciclo: qué desea realizar → texto por líneas → invoca el agente con el texto acumulado.

    Args:
        invoke_agent: función que recibe el mensaje del usuario y devuelve un dict (p. ej. customer_invoke_with_hitl).
    """
    print("\n=== Parche con el supervisor de atención al cliente ===")
    print("Parce, acá va así: va escribiendo el mensaje línea por línea, pues.")
    print(
        "Después de cada Enter le pregunto si ya quedó o si le sigue metiendo. "
        "Si en algún momento quiere salir, escriba exit y listo.\n"
    )

    while True:
        print("Bueno, ¿qué necesita que miremos? Cuénteme:")
        text = _read_multiline_message()
        if text is None:
            print("\nChao pues, parce. Que esté muy bien.\n")
            sys.exit(0)
        if not text:
            print("  Uy, eso quedó pelado, sin nada. Intentemos otra vez, ¿o qué?\n")
            continue

        result = invoke_agent(text)
        _print_playground_result(result)
