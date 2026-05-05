import numpy as np
from sentence_transformers import SentenceTransformer

from rag.ml_quiet import quiet_ml_load

_sentence_model: SentenceTransformer | None = None


def _get_sentence_model() -> SentenceTransformer:
    """Carga el modelo multilingüe una sola vez (primera vez puede descargar ~500MB)."""
    global _sentence_model
    if _sentence_model is None:
        with quiet_ml_load():
            _sentence_model = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
    return _sentence_model


def get_embedding(text: str) -> list[float]:
    """Genera el embedding de un texto usando el modelo multilingüe."""
    return _get_sentence_model().encode(text).tolist()


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Genera embeddings para una lista de textos en batch."""
    return _get_sentence_model().encode(texts).tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calcula la similitud coseno entre dos vectores."""
    a_arr, b_arr = np.array(a), np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))