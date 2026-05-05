"""Suprime ruido de tqdm/transformers al cargar modelos locales (embeddings, cross-encoder)."""

from __future__ import annotations

import contextlib
import logging
import os
import sys


@contextlib.contextmanager
def quiet_ml_load() -> None:
    """
    Durante ``yield``, silencia barras de progreso y LOAD REPORT de HuggingFace/transformers.
    Debe rodear solo la llamada que instancia el modelo (SentenceTransformer, CrossEncoder, etc.).
    """
    env_keys = (
        "HF_HUB_DISABLE_PROGRESS_BARS",
        "HF_HUB_DISABLE_TELEMETRY",
        "TOKENIZERS_PARALLELISM",
    )
    backup: dict[str, str | None] = {k: os.environ.get(k) for k in env_keys}
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    log_names = (
        "transformers",
        "transformers.modeling_utils",
        "sentence_transformers",
        "sentence_transformers.SentenceTransformer",
        "huggingface_hub",
        "torch",
        "urllib3",
    )
    log_levels: list[tuple[logging.Logger, int]] = []
    for name in log_names:
        log = logging.getLogger(name)
        log_levels.append((log, log.level))
        log.setLevel(logging.ERROR)

    try:
        import transformers

        transformers.logging.set_verbosity_error()
    except Exception:
        pass

    old_out, old_err = sys.stdout, sys.stderr
    with open(os.devnull, "w") as dn:
        sys.stdout = dn
        sys.stderr = dn
        try:
            yield
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        for log, prev in log_levels:
            log.setLevel(prev)
        for key, prev in backup.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
