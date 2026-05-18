"""
Cliente Groq dedicado para RAGAS (evaluación): ``AsyncOpenAI`` + ``GROQ_MODEL_CHECK``.

Ragas 0.4 (colección ``metrics.collections``) usa ``agenerate`` y exige cliente async.
"""

from __future__ import annotations

import math
import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    ContextPrecision,
    ContextPrecisionWithoutReference,
    Faithfulness,
)

load_dotenv()


def _groq_base_url() -> str:
    return os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")


def groq_check_model_name() -> str:
    """Modelo usado solo para métricas RAGAS (fall back a GROQ_MODEL)."""
    return os.getenv("GROQ_MODEL_CHECK") or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


@lru_cache(maxsize=1)
def get_groq_ragas_async_client() -> AsyncOpenAI:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY no está configurada (requerida para RAGAS / Faithfulness)."
        )
    return AsyncOpenAI(base_url=_groq_base_url(), api_key=api_key)


@lru_cache(maxsize=1)
def get_ragas_evaluator_llm():
    """Instructor LLM para RAGAS apuntando a Groq con ``GROQ_MODEL_CHECK``."""
    return llm_factory(groq_check_model_name(), client=get_groq_ragas_async_client())


@lru_cache(maxsize=1)
def get_faithfulness_metric() -> Faithfulness:
    return Faithfulness(llm=get_ragas_evaluator_llm())


@lru_cache(maxsize=1)
def get_context_precision_metric() -> ContextPrecision:
    """Context precision **con** referencia (respuesta oro), p. ej. datasets de evaluación."""
    return ContextPrecision(llm=get_ragas_evaluator_llm())


@lru_cache(maxsize=1)
def get_context_precision_without_reference_metric() -> ContextPrecisionWithoutReference:
    """Context precision **sin** referencia: usa la respuesta generada por el RAG."""
    return ContextPrecisionWithoutReference(llm=get_ragas_evaluator_llm())


def compute_faithfulness_score(
    user_input: str,
    response: str,
    retrieved_contexts: list[str],
) -> float | None:
    """
    Faithfulness 0–1 (RAGAS). Devuelve None si faltan datos o el score es NaN.
    """
    if not (user_input or "").strip() or not (response or "").strip():
        return None
    if not retrieved_contexts:
        return None
    result = get_faithfulness_metric().score(
        user_input=user_input.strip(),
        response=response.strip(),
        retrieved_contexts=retrieved_contexts,
    )
    val = result.value
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    return float(val)


def compute_context_precision_with_reference_score(
    user_input: str,
    reference: str,
    retrieved_contexts: list[str],
) -> float | None:
    """
    Context precision con ``reference`` (documentación RAGAS / respuesta esperada).
    """
    if not (user_input or "").strip() or not (reference or "").strip():
        return None
    if not retrieved_contexts:
        return None
    result = get_context_precision_metric().score(
        user_input=user_input.strip(),
        reference=reference.strip(),
        retrieved_contexts=retrieved_contexts,
    )
    val = result.value
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    return float(val)


def compute_context_precision_from_response_score(
    user_input: str,
    response: str,
    retrieved_contexts: list[str],
) -> float | None:
    """
    Context precision sin referencia externa: juzga si los chunks son útiles
    para la ``response`` del modelo (caso típico en producción sin gold answers).
    """
    if not (user_input or "").strip() or not (response or "").strip():
        return None
    if not retrieved_contexts:
        return None
    result = get_context_precision_without_reference_metric().score(
        user_input=user_input.strip(),
        response=response.strip(),
        retrieved_contexts=retrieved_contexts,
    )
    val = result.value
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    return float(val)
